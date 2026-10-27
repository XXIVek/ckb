#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Лог обращения к правилам дерева `rules:` (узел RULES-LOG, 27.10.2026).

Зачем
-----
Правила читают по ходу работы агента, и по одному запуску видно только вывод этого запуска.
Лог отвечает на другой вопрос: к какому правилу обращались, когда именно, чем закончилось
обращение и был ли поднят корень `rules:`. Это нужно для двух разборов: «агент не поднял
общие правила и ответил по памяти» и «это правило читают на каждом шаге, оно раздувается».

Формат
------
Один текстовый файл `logs/rules_load.log`, дозапись. Формата два; по умолчанию — краткий,
потому что вопрос лога один: «когда и какую карточку поднимали». На него отвечает одна строка
на карточку — дата и адрес:

    2026-10-26 22:31:05  rules:
    2026-10-26 22:31:05  rules:kb-rules:

Режима вызова, id, объёма и подсказки в кратком формате нет: это другой вопрос, и он относится
к замерам. Подробный формат включается флагом `--full-log` у читающих инструментов. В нём
сессия = одно обращение к инструменту, и каждая её строка несёт метку процесса `[p<pid>]` —
по ней сессия собирается при любом перемешивании параллельных прогонов:

    ======================================================================
    2026-10-26 22:31:05  ОБРАЩЕНИЕ К ПРАВИЛАМ  [p4242]
      инструмент: tools/rules_read.py
      режим:      --always
    ----------------------------------------------------------------------
    >>> НАЧАЛО ЗАГРУЗКИ ПРАВИЛ: поднят корень дерева `rules:` <<<  [p4242]
    ----------------------------------------------------------------------
    2026-10-26 22:31:05  ЗАГРУЖЕНО  rules:  id=6124  5784 симв.  узел=root  корень=да  [p4242]
                         заголовок: карта слоёв, формат адреса, порядок чтения  [p4242]
    2026-10-26 22:31:05  ИТОГ  карточек 1, символов 5784, промахов 0, корень поднимался=да  [p4242]
    ======================================================================

Заголовок карточки — её адрес (`knowledge_snippets.question`): тем же словом проект называет
заголовок в `normalize_title`. В подробном формате человекочитаемая строка после `заголовок:`
берётся из описательного раздела карточки (`SUMMARY`/`SCOPE`/`WHEN`) и подписана отдельно: это
подсказка, а не второе имя правила.

Оба формата разбираются одними командами (`--tail`, `--stats`, `--check`): файл, где подробный
формат сменился кратким, читается без правок — форматы различаются по метке процесса.

Выделение корня
---------------
В подробном формате обращение к `rules:` помечается блоком `>>> НАЧАЛО ЗАГРУЗКИ ПРАВИЛ <<<` и
полем `корень=да`: по нему видно, что заход начался с общих правил, а не с отдельного адреса.
В кратком формате признаком служит сама строка с адресом корня — отдельного блока там писать
некуда, строка одна. Границу задаёт
`is_tree_root` — на один шире, чем `node_kind`: последний называет `root` и первую карточку
слоя (`rules:core-rules:`), а выделение начала обязано отвечать на вопрос «подняли ли общие
правила», а не «читали ли какую-то карточку слоя». Тип узла в строке при этом остаётся
канонический (`node_kind` модуля `src/rules_layer.py`) — второго определения дерева лог не
заводит. Если корень в обращении не поднимался, `ИТОГ` говорит это прямо: «не поднимался» и
«не поднимался, хотя режим обязан был его поднять» — разные наблюдения.

Чего лог не делает
------------------
Он не меняет вывод инструмента и не влияет на код возврата: ошибка записи называется строкой
в stderr один раз, но чтение правила не отменяет. Лог не хранит содержимое карточек — только
адрес, id, размер и режим обращения; содержимое читают адресом (`tools/rules_read.py`).
Краткий формат не хранит ни режима, ни id, ни объёма, ни промахов: его строка — дата и адрес
карточки, и только. Замерами (объём always-набора, чем закончилось обращение) занимается
подробный формат — `--full-log`.

Запуск
------
    python tools/rules_logging.py --path             # куда пишется лог
    python tools/rules_logging.py --tail 40          # последние строки
    python tools/rules_logging.py --stats            # разбор: частоты обращений, даты
    python tools/rules_logging.py --check            # целость сессий и читаемость строк
    python tools/rules_logging.py --rotate           # перенос лога в logs/archive/

Лог в репозиторий не входит (`logs/` в `.gitignore`): это наблюдение за прогонами, а не
артефакт контракта и не доказательство замера, на которое ссылается норматив.
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _p in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

import rules_layer as RL  # noqa: E402

LOG_DIR = PROJECT_ROOT / "logs"
LOG_NAME = "rules_load.log"
ARCHIVE_DIR = LOG_DIR / "archive"
WIDTH = 72
HINT_CHARS = 150
# Разделы, по которым берут человекочитаемую подсказку: `SUMMARY` отвечает на «что это»,
# `WHEN` — на «когда нужно». Порядок значим: подсказка о карточке важнее подсказки о задаче.
HINT_SECTIONS = ("SUMMARY", "SCOPE", "WHEN")
# После этого размера сессия напоминает о ротации: молча растущий лог через год читается как
# файл, который нельзя открыть, а `--tail` и `--stats` становятся дорогими.
LOG_WARN_BYTES = 512_000

_SESSION_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+ОБРАЩЕНИЕ К ПРАВИЛАМ")
_LOADED_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+ЗАГРУЖЕНО\s+(\S+)")
_MISSED_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+НЕ НАЙДЕНО\s+(\S+)")
_RESULT_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s+ИТОГ\s+(.*)$")
_MODE_RE = re.compile(r"^\s+режим:\s+(.*)$")
_INSTRUMENT_RE = re.compile(r"^\s+инструмент:\s+(.*)$")
_ROOT_RE = re.compile(r"^>>> НАЧАЛО ЗАГРУЗКИ ПРАВИЛ")
# Метка процесса в конце каждой строки. Строки сессии пишутся по одной — иначе прогон,
# прерванный между строками, теряет и остальной текст; значит два параллельных обращения
# могут перемешаться. Молча перемешанные сессии читались бы как одна: «правила не поднимали»,
# хотя поднимали в другом процессе. По метке сессия собирается заново при любом перемешивании.
_TAG_RE = re.compile(r"\s+\[p(\d+)\]\s*$")

# Два формата записи. Краткий — значение по умолчанию: он отвечает на тот единственный вопрос,
# ради которого лог и заводится (когда и какую карточку поднимали). Подробный — другой вопрос,
# замерный: чем закончилось обращение и сколько это весило.
FORMAT_BRIEF = "brief"
FORMAT_FULL = "full"
DEFAULT_FORMAT = FORMAT_BRIEF

# Строка краткого формата: дата и адрес карточки, больше ничего. От подробного формата она
# отличается отсутствием метки процесса, но одной метки мало: правка файла руками не должна
# читаться как обращение к карточке с адресом `ИТОГ`, поэтому служебные слова подробного
# формата адресом не считаются — такая строка называется неразобранной (`stray`), а не
# пропускается молча. `_TS_RE` нужен для той же отчётности: строка начинается с даты, но не
# читается ни одним из форматов.
_BRIEF_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\S+)$")
_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(.*)$")
_BRIEF_STOP = {"ОБРАЩЕНИЕ", "ЗАГРУЖЕНО", "НЕ", "ЗАМЕКА", "ИТОГ", "ПРЕРВАНА"}


def log_path(name=None):
    """Путь лога: каталог создаётся при первой записи, а не при импорте модуля."""
    return LOG_DIR / (name or LOG_NAME)


def stamp(when=None):
    """Метка времени строки лога: локальное время с точностью до секунды."""
    return (when or datetime.datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


def is_tree_root(address):
    """Корень дерева `rules:` — и только он; первую карточку слоя (`rules:core-rules:`) это
    не включает.

    `node_kind` называет `root` и корень дерева, и корень слоя: для проверки целостности
    дерева это одно и то же, для лога — нет. Выделение «НАЧАЛО ЗАГРУЗКИ ПРАВИЛ» отвечает на
    вопрос «подняли ли общие правила», а не «читали ли какую-то карточку слоя», поэтому
    берёт глубину адреса: у корня дерева сегментов один.
    """
    return (RL.node_kind(address) == RL.KIND_ROOT
            and RL.levels_of(address) <= 1
            and RL.marker_of(address) == RL.ROOT_MARKER)


def _hint_line(text):
    """Строка подсказки: одна строка, без машинных маркеров раздела.

    `section_bodies` отдаёт содержимое, начиная сразу за именем якоря — то есть первой строкой
    тела идёт закрывающая часть якоря (`===`). Молча оставить её значило бы начать подсказку
    с `===`, а не с текста; тот же маркер встречается в карточках прежнего формата как
    перечисление, и он тоже не относится к подсказке.
    """
    return " ".join(str(text or "").split()).lstrip("= \t").strip()


def card_hint(card):
    """Человекочитаемая подсказка к заголовку: первая строка описательного раздела.

    Берётся из `section_bodies` модуля `src/rules_layer.py` — тех же разделов, по которым
    правило проверяет `check_rules_layer.py`. Если описательного раздела нет, подсказкой
    становится первая непустая строка карточки без машинных маркеров: пустая подсказка в логе
    читалась бы как «карточка пустая», тогда как на самом деле раздел не подписан.
    """
    answer = (card or {}).get("answer") or ""
    bodies = RL.section_bodies(answer)
    candidates = [bodies.get(name) or "" for name in HINT_SECTIONS]
    candidates.append(answer)
    for body in candidates:
        for line in body.splitlines():
            text = _hint_line(line)
            if text:
                return text[:HINT_CHARS] + ("…" if len(text) > HINT_CHARS else "")
    return "(подсказки нет: ни описательного раздела, ни текста у карточки нет)"


class RulesLog:
    """Одно обращение к правилам.

    Подробный формат — сессия: шапка, строки загрузки, итог. Краткий (значение по умолчанию) —
    по одной строке «дата + адрес» на прочитанную карточку, без шапки и без итога.

    Экземпляр с `enabled=False` (режим `--no-log`) сохраняет тот же интерфейс и молчит:
    вызывающему коду не нужны проверки «включено ли логирование», и однажды пропущенный
    вызов не превращается в расхождение между двумя режимами запуска. Счётчики (`count`,
    `total_chars`, `root_logged`) считаются в обоих форматах: вызывающий код печатает свой
    вывод одинаково, и разошедшиеся форматы дали бы дефект инструмента, а не лога.
    """

    def __init__(self, tool, mode, path=None, enabled=True, fmt=DEFAULT_FORMAT):
        if fmt not in (FORMAT_BRIEF, FORMAT_FULL):
            print(f"ПРЕДУПРЕЖДЕНИЕ: неизвестный формат лога {fmt!r} — пишется "
                  f"{DEFAULT_FORMAT}", file=sys.stderr)
            fmt = DEFAULT_FORMAT
        self.tool = str(tool or "")
        self.mode = str(mode or "")
        self.path = Path(path) if path else log_path()
        self.enabled = bool(enabled)
        self.fmt = fmt
        self.brief = fmt == FORMAT_BRIEF
        self.pid = os.getpid()
        self.started = False
        self.closed = False
        self.root_logged = False
        # Отдельно от root_logged: признак того, что выделенный блок подробного формата уже
        # напечатан. root_logged отвечает на вопрос «поднимали ли корень» и ставится в обоих
        # форматах; блок — только в подробном и только один раз за обращение.
        self.root_block = False
        self.count = 0
        self.missed_count = 0
        self.total_chars = 0
        self._fh = None
        self._warned = False

    # ------------------------------------------------------------- запись
    def _fail(self, exc):
        """Ошибка лога не отменяет чтение правила — она называется один раз."""
        if not self._warned:
            self._warned = True
            print(f"ПРЕДУПРЕЖДЕНИЕ: лог правил не пишется ({self.path}): {exc}",
                  file=sys.stderr)
        self.enabled = False

    def _rotation_warning(self, size):
        """Предупреждение о размере лога — в stderr, а не строкой файла.

        В кратком формате строке лога не место: она обязана быть датой и адресом карточки, а
        предупреждение адресом не является и было бы разобрано как обращение к карточке
        `ПРЕДУПРЕЖДЕНИЕ:`. Молчать о разросшемся логе при этом нельзя — его перестанут
        читать.
        """
        print(f"ПРЕДУПРЕЖДЕНИЕ: лог {self.path} весит {size} байт (> {LOG_WARN_BYTES}) — "
              "нужна ротация: python tools/rules_logging.py --rotate", file=sys.stderr)

    def _line(self, text, tag=True):
        """Одна строка лога, записанная сразу.

        Копить до конца сессии нельзя: процесс, убитый между строками, потерял бы весь текст,
        и оборванный прогон был бы неотличим от несостоявшегося. Поэтому строка уходит сразу,
        а принадлежность сессии держит метка процесса в конце строки.
        """
        if not self.enabled:
            return
        line = str(text)
        if tag:
            line = f"{line}  [p{self.pid}]"
        try:
            if self._fh is None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._fh = open(self.path, "a", encoding="utf-8", newline="\n")
            self._fh.write(line + "\n")
            self._fh.flush()
        except (OSError, UnicodeError) as exc:
            self._fail(exc)

    # ------------------------------------------------------------- сессия
    def start(self):
        if not self.enabled or self.started:
            return self
        self.started = True
        try:
            size = self.path.stat().st_size if self.path.exists() else 0
        except OSError:
            size = 0
        if size > LOG_WARN_BYTES and self.brief:
            self._rotation_warning(size)
        if self.brief:
            # Шапки сессии в кратком формате нет: режим вызова в строку «дата + адрес» не
            # помещается, а шапка без режима была бы шумом между двумя строками карточек.
            return self
        self._line("=" * WIDTH, tag=False)
        self._line(f"{stamp()}  ОБРАЩЕНИЕ К ПРАВИЛАМ")
        self._line(f"  инструмент: {self.tool}")
        self._line(f"  режим:      {self.mode}")
        if size > LOG_WARN_BYTES:
            self._line(f"  ⚠️ размер лога {size} байт (> {LOG_WARN_BYTES}) — нужна ротация: "
                       "python tools/rules_logging.py --rotate")
        self._line("-" * WIDTH, tag=False)
        return self

    def loaded(self, card, note=None):
        """Строка загрузки: заголовок (адрес) и время; в кратком формате — только они.

        Счётчики и признак поднятого корня считаются до ветки формата: вызывающий код по ним
        печатает собственный вывод, и он не должен различаться в зависимости от того, какой
        формат пишет файл.
        """
        if not self.enabled or card is None:
            return self
        address = str(card.get("address") or "")
        kind = RL.node_kind(address)
        root = is_tree_root(address)
        self.count += 1
        self.total_chars += int(card.get("size") or 0)
        if root:
            self.root_logged = True
        if self.brief:
            self._line(f"{stamp()}  {address}", tag=False)
            return self
        if root and not self.root_block:
            self.root_block = True
            self._line("-" * WIDTH, tag=False)
            self._line(f">>> НАЧАЛО ЗАГРУЗКИ ПРАВИЛ: поднят корень дерева "
                       f"`{RL.ROOT_MARKER}:` <<<")
            self._line("-" * WIDTH, tag=False)
        self._line(f"{stamp()}  ЗАГРУЖЕНО  {address}  id={card.get('id')}  "
                   f"{int(card.get('size') or 0)} симв.  узел={kind or '?'}"
                   + ("  корень=да" if root else ""))
        self._line(f"{'':21}заголовок: {card_hint(card)}")
        if note:
            self._line(f"{'':21}примечание: {' '.join(str(note).split())}")
        return self

    def missed(self, query, note=None):
        """Обращение, которое карточкой не кончилось: «правил нет» тоже событие.

        В кратком формате оно не пишется: строка краткого формата — адрес прочитанной
        карточки, а у промаха карточки нет. Промахи относятся к замерному вопросу, для
        которого есть подробный формат.
        """
        if not self.enabled:
            return self
        self.missed_count += 1
        if self.brief:
            return self
        self._line(f"{stamp()}  НЕ НАЙДЕНО  {query}"
                   + (f"  ({' '.join(str(note).split())})" if note else ""))
        return self

    def note(self, text):
        """Служебная строка: чем закончился режим, когда карточки целиком не читались."""
        if not self.enabled or self.brief:
            return self
        self._line(f"{stamp()}  ЗАМЕКА  {' '.join(str(text).split())}")
        return self

    def finish(self):
        """Итог обращения: число карточек, объём и поднимался ли корень.

        В кратком формате итога нет — итоговая строка не является адресом карточки. Файл при
        этом закрывается: дескриптор не должен переживать вызов.
        """
        if not self.enabled or self.closed:
            return self
        self.closed = True
        if self.brief:
            self.close()
            return self
        self._line(f"{stamp()}  ИТОГ  карточек {self.count}, символов {self.total_chars}, "
                   f"промахов {self.missed_count}, корень поднимался="
                   + ("да" if self.root_logged else "нет"))
        self._line("=" * WIDTH, tag=False)
        self.close()
        return self

    def interrupted(self, exc_type, exc):
        """Итог прерванной сессии: причина называется строкой, а не молчанием.

        Строка остаётся строкой `ИТОГ` — иначе проверка формата приняла бы аварию за
        оборванный лог, — но содержит «сессия прервана»: сводка по такому логу занижена,
        и это видно по тексту итога.
        """
        if not self.enabled or self.closed:
            return self
        self.closed = True
        if self.brief:
            # Причина аварии в кратком формате не пишется: строка лога — адрес карточки,
            # а выдуманного адреса `сессия прервана` в дереве нет. Авария остаётся
            # исключением, которое вызывающий код видит сам.
            self.close()
            return self
        name = getattr(exc_type, "__name__", str(exc_type))
        reason = " ".join(str(exc or "").split())[:160]
        self._line(f"{stamp()}  ИТОГ  карточек {self.count}, символов {self.total_chars}, "
                   f"промахов {self.missed_count}, "
                   f"корень поднимался={'да' if self.root_logged else 'нет'}, "
                   f"сессия прервана: {name}: {reason}")
        self._line("=" * WIDTH, tag=False)
        self.close()
        return self

    def close(self):
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.finish()
        else:
            self.interrupted(exc_type, exc)
        return False


def open_session(tool, mode, path=None, enabled=True, fmt=DEFAULT_FORMAT):
    """Открыть обращение лога; `enabled=False` — тот же интерфейс, но молча.

    `fmt` — формат записи: `FORMAT_BRIEF` (значение по умолчанию) или `FORMAT_FULL` для
    замеров. Неизвестное значение не подменяется молча: о нём говорится строкой в stderr.
    """
    return RulesLog(tool, mode, path=path, enabled=enabled, fmt=fmt)


def null_log():
    """Лог-заглушка для значений по умолчанию: интерфейс тот же, записи нет."""
    return RulesLog("", "", enabled=False)


# ---------------------------------------------------------------------- разбор лога
def read_lines(path):
    """Строки лога; пустой список, если файла ещё нет (первый запуск — не ошибка)."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def parse_log(lines):
    """Разбор строк лога: сессии подробного формата, строки краткого, неразобранные строки.

    Форматы различаются по метке процесса: строки краткого формата её не несут. Признака
    версии в файле нет и не нужен — смешанный файл (сначала подробный, потом краткий)
    разбирается как есть.

    Подробный формат собирается по сессиям, а не по порядку строк. Строки пишутся по одной
    (обрванный прогон не должен терять остальной текст), поэтому два параллельных обращения
    перемешиваются — разбор по порядку приписал бы загрузки чужой сессии и сказал бы «корень
    не поднимали» там, где поднимали в другом процессе.

    Разбор устойчив к обрыву: сессия без `ИТОГ` остаётся в ответе с `result=None` — молча
    потерять её значило бы занижить число обращений. Строки без метки, которые не читаются и
    кратким форматом (разделители, ручная правка файла), событийного смысла не имеют и
    пропускаются; но строка, которая начинается с даты и не читается ни одним форматом,
    в ответ идёт отдельно (`stray`) — молча пройти мимо неё значило бы принять порчу формата
    за чистоту. Повторный заголовок того же pid открывает новую сессию, потому что pid
    переиспользуется.
    """
    sessions = []
    brief = []
    stray = []
    active = {}
    for raw in lines:
        tag = _TAG_RE.search(raw)
        if not tag:
            m = _BRIEF_RE.match(raw)
            if m:
                if m.group(2) in _BRIEF_STOP:
                    stray.append((m.group(1), raw))
                else:
                    brief.append((m.group(1), m.group(2)))
            else:
                m = _TS_RE.match(raw)
                if m:
                    stray.append((m.group(1), raw))
            continue
        pid = tag.group(1)
        line = _TAG_RE.sub("", raw)
        m = _SESSION_RE.match(line)
        if m:
            session = {"ts": m.group(1), "pid": pid, "mode": "", "root": False,
                       "loads": [], "missed": [], "result": None}
            sessions.append(session)
            active[pid] = session
            continue
        session = active.get(pid)
        if session is None:
            session = {"ts": None, "pid": pid, "mode": "(заголовок не дошёл)", "root": False,
                       "loads": [], "missed": [], "result": None}
            sessions.append(session)
            active[pid] = session
        if _ROOT_RE.match(line):
            session["root"] = True
            continue
        m = _MODE_RE.match(line)
        if m:
            session["mode"] = m.group(1).strip()
            continue
        m = _LOADED_RE.match(line)
        if m:
            session["loads"].append((m.group(1), m.group(2)))
            continue
        m = _MISSED_RE.match(line)
        if m:
            session["missed"].append(m.group(2))
            continue
        m = _RESULT_RE.match(line)
        if m:
            session["result"] = m.group(1).strip()
    return {"sessions": sessions, "brief": brief, "stray": stray}


def cmd_path(args):
    print(log_path(args.log_file))
    return 0


def cmd_tail(args):
    """Хвост лога: последние строки вместе с числом строк в файле."""
    path = log_path(args.log_file)
    lines = read_lines(path)
    if not lines:
        print(f"ЛОГА ЕЩЁ НЕТ: {path}")
        return 0
    print(f"ПОСЛЕДНИЕ {args.tail} СТРОК: {path} (всего строк {len(lines)})")
    for line in lines[-args.tail:]:
        print(line)
    return 0


def cmd_stats(args):
    """Сводка по логу: сколько обращений было, с какими режимами и к каким заголовкам.

    Оба формата считаются вместе: вопрос «как часто читают это правило» одинаков для краткого
    и подробного файла. Раздельными становятся только те поля, которых в кратком формате нет
    (режим вызова, итог обращения), — они и подписаны как поля подробного формата.
    """
    path = log_path(args.log_file)
    lines = read_lines(path)
    if not lines:
        print(f"ЛОГА ЕЩЁ НЕТ: {path}")
        return 0
    size = path.stat().st_size
    parsed = parse_log(lines)
    sessions, brief, stray = parsed["sessions"], parsed["brief"], parsed["stray"]
    modes, addresses, last_seen = {}, {}, {}
    root_sessions = broken = halted = full_loads = 0
    for session in sessions:
        key = session["mode"] or "(не указан)"
        modes[key] = modes.get(key, 0) + 1
        root_sessions += 1 if session["root"] else 0
        result = session["result"]
        broken += 1 if result is None else 0
        halted += 1 if result and "сессия прервана" in result else 0
        full_loads += len(session["loads"])
        for ts, address in session["loads"]:
            addresses[address] = addresses.get(address, 0) + 1
            last_seen[address] = max(last_seen.get(address, ""), ts)
    root_brief = 0
    for ts, address in brief:
        addresses[address] = addresses.get(address, 0) + 1
        last_seen[address] = max(last_seen.get(address, ""), ts)
        root_brief += 1 if is_tree_root(address) else 0
    formats = []
    if sessions:
        formats.append(f"подробный (сессий {len(sessions)})")
    if brief:
        formats.append(f"краткий (строк {len(brief)})")
    print(f"СВОДКА ЛОГА: {path}")
    print(f"  строк: {len(lines)}, размер: {size} байт")
    print(f"  формат в файле: {' + '.join(formats) if formats else 'различимых строк нет'}")
    period = [s["ts"] for s in sessions if s["ts"]] + [ts for ts, _ in brief]
    if period:
        print(f"  период: {min(period)} .. {max(period)}")
    if sessions:
        print(f"  сессий подробного формата: {len(sessions)}, с корнем `{RL.ROOT_MARKER}:`: "
              f"{root_sessions}, прерванных (авария названа): {halted}, без итога (обрванных): "
              f"{broken}")
    if brief:
        print(f"  строк краткого формата: {len(brief)}, из них обращений к корню "
              f"`{RL.ROOT_MARKER}:`: {root_brief} (режим вызова, объём и промахи в этом "
              f"формате не пишутся — для них есть --full-log)")
    if stray:
        print(f"  строк, которые формат не читает: {len(stray)} — подробности: --check")
    print(f"  загрузок карточек: {full_loads + len(brief)}")
    if modes:
        print("\n  РЕЖИМЫ ОБРАЩЕНИЙ (только подробный формат)")
        for mode, count in sorted(modes.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"    {count:>4}  {mode}")
    print("\n  ОБРАЩЕНИЯ К ЗАГОЛОВКАМ (частота, последнее обращение)")
    for address, count in sorted(addresses.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"    {count:>4}  {address}  {last_seen.get(address, '')}")
    return 0


def cmd_check(args):
    """Формат лога: подробная сессия закрыта итогом, краткая строка читается адресом.

    Код возврата 1 — формат нарушен. Для подробного формата нарушением считается оборванная
    сессия: часть заголовков в статистику не попала, и сводка по такому логу занижена. Для
    краткого формата сессий нет вовсе, поэтому проверяется сама строка: дата и адрес; строка,
    которая начинается с даты и не читается ни одним форматом, — порча файла, и молча пройти
    её нельзя.
    """
    path = log_path(args.log_file)
    lines = read_lines(path)
    if not lines:
        print(f"ЛОГА ЕЩЁ НЕТ: {path}")
        return 0
    parsed = parse_log(lines)
    sessions, brief, stray = parsed["sessions"], parsed["brief"], parsed["stray"]
    broken = [s for s in sessions if s["result"] is None]
    halted = [s for s in sessions if s["result"] and "сессия прервана" in s["result"]]
    print(f"ПРОВЕРКА ФОРМАТА: {path}")
    if sessions:
        print(f"  подробный формат — сессий: {len(sessions)}, закрытых итогом: "
              f"{len(sessions) - len(broken)}, в том числе прерванных аварией: {len(halted)}, "
              f"без итога: {len(broken)}")
    if brief:
        print(f"  краткий формат — строк: {len(brief)}, разобрано дат и адресов: {len(brief)} "
              f"(сессий этот формат не разделяет, проверяется каждая строка)")
    if not sessions and not brief:
        print("  ни одной строки формата не найдено")
    for session in halted:
        print(f"    ПРЕРЫВ: {session['ts']}  режим={session['mode'] or '(не указан)'}  "
              f"{session['result']}")
    for session in broken:
        print(f"    ОБРЫВ: {session['ts']}  режим={session['mode'] or '(не указан)'}  "
              f"карточек прочитано: {len(session['loads'])}")
    for ts, text in stray:
        print(f"    СТРОКА НЕ ЧИТАЕТСЯ: {ts}  {text}")
    if broken or stray:
        print("ИТОГ: формат нарушен — проблемные строки названы выше.")
        return 1
    if halted:
        print("ИТОГ: формат корректен; прерванные сессии названы выше — сводка по такому "
              "логу занижена.")
        return 0
    print("ИТОГ: формат корректен — сессии закрыты итогом, строки краткого формата читаются.")
    return 0


def cmd_rotate(args):
    """Перенос лога в архив: рабочий файл снова пуст, история остаётся читаемой."""
    path = log_path(args.log_file)
    if not path.exists():
        print(f"РОТАЦИИ НЕТ: файла лога не существует — {path}")
        return 0
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    target = ARCHIVE_DIR / (path.stem + "_"
                            + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + path.suffix)
    shutil.move(str(path), str(target))
    print(f"ЛОГ ПЕРЕНЕСЁН: {path} -> {target}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Чтение и разбор лога обращения к правилам (пишет его tools/rules_logging.py).")
    parser.add_argument("--log-file", help=f"имя файла лога в каталоге {LOG_DIR} "
                                          f"(по умолчанию {LOG_NAME})")
    parser.add_argument("--path", action="store_true", help="показать путь лога")
    parser.add_argument("--tail", type=int, metavar="N", help="показать последние N строк")
    parser.add_argument("--stats", action="store_true",
                        help="сводка: частота обращений к заголовкам, режимы, период")
    parser.add_argument("--check", action="store_true",
                        help="проверить формат: сессии закрыты итогом, строки читаются")
    parser.add_argument("--rotate", action="store_true", help=f"перенести лог в {ARCHIVE_DIR}")
    args = parser.parse_args(argv)
    if args.path:
        return cmd_path(args)
    if args.tail:
        return cmd_tail(args)
    if args.stats:
        return cmd_stats(args)
    if args.check:
        return cmd_check(args)
    if args.rotate:
        return cmd_rotate(args)
    parser.print_help()
    print(f"\nФайл лога: {log_path(args.log_file)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())




