#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V25: мост «бинарный файл внешнего объекта → каталог выгрузки → БД».

Внешние объекты приходят к нам не каталогом XML, а скомпилированными файлами: `.erf`
(внешний отчёт) и `.epf` (внешняя обработка). Загрузчик `load_catalog` читает только каталог
выгрузки (правило R1), поэтому перед ним нужен шаг конвертации. Делает его `ibcmd` из платформы
1С:Предприятие; норматив и все замеры контракта — docs/CONFIGURATIONS_ENRICHMENT_PLAN.md,
раздел 13 (узлы V24, V24.1, V25).

Что подтверждено живыми замерами и учтено здесь (номера правил — из раздела 13.2):

  * L1: `config export/import` работают только с контекстом информационной базы — нужен
    `--db-path`; создание файловой ИБ дешёвое (4.6 с), но каталог с `1Cv8.1CD` размещают
    осознанно и удаляет вызывающая сторона (ibcmd его не удаляет);
  * L3: команды `config info` в CLI нет — состояние конфигурации нельзя спросить у ibcmd,
    поэтому обёртка ведёт собственную метку состояния и ОБОЗНАЧАЕТ её фактом разбора;
  * L4: `rc=0` не гарантирует результата — при отсутствующем входном файле export вернул rc=0,
    «успешно завершено» и ни одного созданного файла. Значим только факт: ожидаемые
    `<база>.xml` и `<база>/` существуют;
  * L8: имена файлов содержимого у ibcmd совпадают с эталонной выгрузкой, расхождений нет;
  * A1 (закрыта 15.10.2026, шаги G1–G7): имена типов (`cfg:CatalogRef.Организации`) появляются,
    если в ИБ **загружена** конфигурация (`config load <файл.cf>`, 99 с на БП3); `config apply`
    для этого не нужен. Без конфигурации тот же файл даёт `<v8:TypeId>` вместо имён — обёртка
    обязана назвать это прямо, а не показать пустой тип;
  * A2: дорогая часть одноразовая (создание ИБ + загрузка конфигурации ≈104 с), повторная
    конвертация — 13–15 с, поэтому ИБ переиспользуется, а не создаётся на каждый файл;
  * именование вывода: `export … <база>` даёт пару `<база>.xml` + `<база>/`; лишний суффикс
    `.xml` в аргументе даёт `<база>.xml.xml`. Пару `<база>.xml` + `<база>/` загрузчик принимает
    как есть: `base_path = parent(корневого XML)/stem(корневого XML)`
    (src/external_report_loader.py, узел V10) — переименовывать каталог в имя объекта не нужно.
    У внешнего объекта с пустым содержимым каталог `<база>/` не создаётся вовсе (замер узла
    V29, 16.10.2026): значимый артефакт разбора — `<база>.xml`, отсутствие каталога —
    предупреждение, а не отказ.

Слоем ниже этот модуль ничего не знает о БД: загрузку выполняет `config_load_router.load_catalog`
(его четыре исхода и формат карточки не меняются). Точка входа MCP —
server_configurations_core.py::load_external_object_file_tool (тонкая обёртка).
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Вид внешнего объекта по расширению скомпилированного файла. Соответствие закреплено самим CLI:
# `ibcmd help config` описывает --file как «путь к файлу конфигурации, расширения конфигурации,
# внешней обработки или отчета» (раздел 13.1, п. 9).
BINARY_KINDS = {
    ".erf": "external_report",
    ".epf": "external_processing",
}

# Каталог работы по умолчанию: внутри проекта, а не в C:\TMP (его чистит внешний процесс —
# вместе с прогоном пропали и скрипт, и созданная ИБ). Каталог ИБ переиспользуется.
DEFAULT_WORK_DIR = PROJECT_ROOT / "_ibcmd_work"
DEFAULT_DB_PATH = DEFAULT_WORK_DIR / "ib"

# Таймауты по замерам (13.6): конвертация 13–15 с, загрузка конфигурации БП3 — 99 с.
# Пороги с запасом: зависший процесс не должен держать вызов бесконечно.
TIMEOUT_INFOBASE = 300
TIMEOUT_EXPORT = 600
TIMEOUT_LOAD_CONFIG = 3600

STATE_FILE_NAME = "ckb_ibcmd_state.json"

# Точки состояния конфигурации в ИБ (L3: спросить у ibcmd нельзя, ведём свою метку).
CONFIG_STATE_UNKNOWN = "unknown"
CONFIG_STATE_LOADED = "loaded"
CONFIG_STATE_FAILED = "load_failed"


def _decode(raw):
    """ibcmd пишет в консоль OEM-кодировку (cp866), иногда UTF-8 — перебираем варианты."""
    for enc in ("utf-8", "cp866", "cp1251"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, AttributeError):
            continue
    return (raw or b"").decode("utf-8", "replace")


def _error(reason, hint=""):
    return {"success": False, "status": "error", "error": reason, "hint": hint}


def _stage(result, stage):
    """Пометить, на какой стадии закончился вызов: `conversion` или `load`.

    Граница нужна формату ответа: «разбор не выполнен» и «разбор выполнен, загрузчик отказал»
    — разные ответы, и смешивать их в одну карточку нельзя (правило R13, 13.7).
    """
    answer = dict(result)
    answer["stage"] = stage
    return answer


def _platform_candidates():
    """Каталоги установленных платформ (старшие версии первыми)."""
    roots = [r"C:\Program Files\1cv8", r"C:\Program Files (x86)\1cv8"]
    found = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        found.extend(glob.glob(os.path.join(root, "*", "bin", "ibcmd.exe")))

    def version_key(path):
        parts = re.findall(r"\d+", path)
        return [int(p) for p in parts] or [0]

    return sorted(found, key=version_key, reverse=True)


def find_ibcmd():
    """Найти ibcmd.exe: сначала PATH, потом каталоги платформы по убыванию версии.

    Возвращает {"success": True, "path", "version"} либо явную причину отказа: молча не
    конвертировать нельзя (L3 — метаданные бинаря даёт только разбор).
    """
    found = shutil.which("ibcmd") or shutil.which("ibcmd.exe")
    candidates = [found] if found else []
    candidates += _platform_candidates()
    for path in candidates:
        if not path or not os.path.isfile(path):
            continue
        version = ""
        try:
            proc = subprocess.run([path, "--version"], capture_output=True, timeout=60)
            version = _decode(proc.stdout).strip() or _decode(proc.stderr).strip()
        except (OSError, subprocess.SubprocessError):
            version = ""
        return {"success": True, "path": path, "version": version}
    return _error(
        "ibcmd не найден: ни в PATH, ни в каталогах платформы (C:\\Program Files\\1cv8\\*\\bin).",
        "Нужна установленная платформа 1С:Предприятие: конвертацию .erf/.epf делает её утилита "
        "ibcmd. Альтернативы в этом проекте нет (L3).",
    )


def _run_ibcmd(ibcmd_path, args, timeout):
    """Вызвать ibcmd, вернуть rc/выводы/время. Исключение не бросает: TIMEOUT — тоже исход."""
    started = time.time()
    try:
        proc = subprocess.run([ibcmd_path] + list(args), capture_output=True, timeout=timeout)
        return {"rc": proc.returncode, "stdout": _decode(proc.stdout).strip(),
                "stderr": _decode(proc.stderr).strip(),
                "seconds": round(time.time() - started, 1), "timed_out": False}
    except subprocess.TimeoutExpired:
        return {"rc": "TIMEOUT", "stdout": "", "stderr": f"команда прервана по таймауту {timeout}с",
                "seconds": round(time.time() - started, 1), "timed_out": True}
    except OSError as exc:
        return {"rc": "EXEC_ERROR", "stdout": "", "stderr": repr(exc),
                "seconds": round(time.time() - started, 1), "timed_out": False}


def infobase_exists(db_path):
    """Есть ли в каталоге файловая база (1Cv8.1CD / 1Cv8.1CD.cfl)."""
    try:
        return bool(list(Path(db_path).glob("1Cv8.1CD*")))
    except OSError:
        return False


def _state_path(db_path):
    return Path(db_path) / STATE_FILE_NAME


def read_state(db_path):
    """Метка состояния ИБ (L3: у ibcmd нет команды «показать состояние конфигурации»)."""
    try:
        with open(_state_path(db_path), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(db_path, data):
    try:
        Path(db_path).mkdir(parents=True, exist_ok=True)
        with open(_state_path(db_path), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        return True
    except OSError:
        return False


def ensure_infobase(db_path=None, timeout=TIMEOUT_INFOBASE):
    """Создать файловую ИБ, если её ещё нет; существующую не трогать (переиспользование, A2)."""
    db_path = os.path.abspath(str(db_path or DEFAULT_DB_PATH))
    if infobase_exists(db_path):
        return {"success": True, "created": False, "db_path": db_path, "seconds": 0.0}

    ib = find_ibcmd()
    if not ib.get("success"):
        return ib
    Path(db_path).mkdir(parents=True, exist_ok=True)
    # --db-path только абсолютный: относительные пути ibcmd разрешает от каталога данных
    # автономного сервера, и там ИБ теряется (замер, сниппет local_doc 4640).
    run = _run_ibcmd(ib["path"], ["infobase", "create", "--db-path", db_path,
                                  "--create-database", "--locale=ru"], timeout)
    if run["rc"] != 0 or not infobase_exists(db_path):
        return _error(
            f"Не удалось создать информационную базу в {db_path}: rc={run['rc']}",
            run["stderr"] or run["stdout"] or "ibcmd не сообщил причину",
        )
    state = {"created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "config_state": CONFIG_STATE_UNKNOWN}
    write_state(db_path, state)
    return {"success": True, "created": True, "db_path": db_path, "seconds": run["seconds"],
            "state": state}


def configuration_state(db_path=None):
    """Состояние конфигурации в ИБ по метке обёртки (L3).

    Значение фактом не является: реальное представление типов проверяется по разобранному XML
    (type_name_counts). Метка нужна только чтобы не грузить конфигурацию повторно.
    """
    return read_state(os.path.abspath(str(db_path or DEFAULT_DB_PATH))).get(
        "config_state", CONFIG_STATE_UNKNOWN)


def type_name_counts(root_xml):
    """Сколько в разобранном XML имён типов (`cfg:`) и сколько идентификаторов (`<v8:TypeId>`).

    Это не статистика «для отчёта», а факт о контексте (L5/A1): при загруженной конфигурации
    ibcmd отдаёт имена, без неё — только идентификаторы. Счётчик читает уже сохранённый разбор,
    конфигуратор не открывается.
    """
    try:
        with open(root_xml, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        return {"available": False, "reason": repr(exc)}
    cfg_names = len(re.findall(r"<v8:Type>\s*cfg:", text))
    type_ids = len(re.findall(r"<(?:v8|xr):TypeId>", text))
    return {"available": True, "cfg_type_names": cfg_names, "type_id_elements": type_ids,
            "types_resolved": cfg_names > 0}


def export_to_layout(binary_path, out_base, db_path=None, timeout=TIMEOUT_EXPORT):
    """Конвертировать .erf/.epf в каталог выгрузки: `<база>.xml` + каталог `<база>/`.

    Решение о результате — по существованию файлов, а не по коду возврата (L4: при отсутствующем
    входном файле ibcmd вернул rc=0, «успешно завершено» и ни одного файла).

    Обязательный артефакт — `<база>.xml`; каталог `<база>/` опционален (замер узла V29,
    16.10.2026: `config export` собранного .epf внешней обработки с пустым содержимым
    создал `<база>.xml` и НЕ создал `<база>/`, при этом отчёт — «Экспорт конфигурации в
    XML успешно завершен», rc=0). Требовать каталог у объекта без содержимого — значит
    отрицать факт успешного разбора; содержимое с каталогом считается как раньше
    (`content_files` считает файлы каталога), а объект с объявленными, но отсутствующими
    формами виден не здесь, а в карточке загрузки (её предупреждениями о детях).
    """
    binary_path = os.path.abspath(str(binary_path))
    out_base = os.path.abspath(str(out_base))
    db_path = os.path.abspath(str(db_path or DEFAULT_DB_PATH))
    if not os.path.isfile(binary_path):
        return _error(f"Файл внешнего объекта не найден: {binary_path}",
                      "Проверьте путь: нужен .erf (отчёт) или .epf (обработка).")
    if not infobase_exists(db_path):
        return _error(
            f"Информационная база для ibcmd не подготовлена: {db_path}",
            "L1: без контекста ИБ `config export` отказывается работать; нужен каталог с "
            "1Cv8.1CD (ensure_infobase).",
        )

    ib = find_ibcmd()
    if not ib.get("success"):
        return ib

    # Лишний суффикс .xml в базе вывода даёт <база>.xml.xml — убираем (замер, 13.6 п. 5).
    if out_base.lower().endswith(".xml"):
        out_base = out_base[:-4]
    Path(os.path.dirname(out_base)).mkdir(parents=True, exist_ok=True)

    run = _run_ibcmd(ib["path"], ["config", "--db-path", db_path, "export",
                                  "--file=" + binary_path, out_base], timeout)

    root_xml = out_base + ".xml"
    content_dir = out_base
    warnings = []
    if not os.path.exists(root_xml):
        return _error(
            "ibcmd завершился (rc=%s), но корневой XML выгрузки не создал: %s"
            % (run["rc"], root_xml),
            run["stderr"] or run["stdout"] or "файлов нет; причину от ibcmd получить не удалось",
        )
    if not os.path.isdir(content_dir):
        # Пустое содержимое — штатное состояние внешнего объекта (замер V29), не ошибка.
        content_dir = None
        warnings.append(
            "Каталог содержимого %s не создан: у объекта пустое содержимое "
            "(форм, макетов и модулей в выгрузке нет) — это не ошибка разбора." % out_base
        )

    files = [p for p in Path(content_dir).rglob("*") if p.is_file()] if content_dir else []
    return {"success": True, "ibcmd": ib["path"], "ibcmd_version": ib["version"],
            "binary": binary_path, "root_xml": root_xml,
            "layout_dir": os.path.dirname(root_xml), "object_dir": content_dir,
            "content_files": len(files), "seconds": run["seconds"], "rc": run["rc"],
            "warnings": warnings, "type_names": type_name_counts(root_xml)}


def import_from_layout(root_xml, out_binary, db_path=None, timeout=TIMEOUT_EXPORT):
    """Обратная сторона (для узла V18): каталог выгрузки → .erf/.epf.

    Требует ИБ с нужной конфигурацией: на пустой ИБ импорт XML с `cfg:`-типами даёт
    «Неизвестное имя типа - CatalogRef.…» и критичные ошибки (L6; снимается только при
    загруженной конфигурации — A1).
    """
    root_xml = os.path.abspath(str(root_xml))
    out_binary = os.path.abspath(str(out_binary))
    db_path = os.path.abspath(str(db_path or DEFAULT_DB_PATH))
    if not os.path.isfile(root_xml):
        return _error(f"Корневой XML не найден: {root_xml}",
                      "Нужен XML внешнего объекта; каталог содержимого рядом обязателен только "
                      "при непустом содержимом объекта.")
    ib = find_ibcmd()
    if not ib.get("success"):
        return ib
    run = _run_ibcmd(ib["path"], ["config", "--db-path", db_path, "import", root_xml,
                                  "--out=" + out_binary], timeout)
    if run["rc"] != 0 or not os.path.isfile(out_binary):
        return _error(f"Собрать файл внешнего объекта не удалось: rc={run['rc']}",
                      run["stderr"] or run["stdout"] or "файл не создан")
    return {"success": True, "binary": out_binary, "bytes": os.path.getsize(out_binary),
            "seconds": run["seconds"], "rc": run["rc"]}


def load_configuration(db_path=None, config_file=None, timeout=TIMEOUT_LOAD_CONFIG):
    """Загрузить конфигурацию в ИБ (`config load <файл.cf>`) — закрытие точки A1.

    `config apply` (обновление конфигурации базы данных) не выполняется: замер 15.10.2026
    показал, что для разрешения имён типов достаточно загруженной конфигурации (99 с на БП3),
    а `apply` добавляет ещё 155 с и ничего к разрешению имён не даёт.
    """
    db_path = os.path.abspath(str(db_path or DEFAULT_DB_PATH))
    if not config_file or not os.path.isfile(str(config_file)):
        return _error(
            f"Файл конфигурации не найден: {config_file}",
            "Нужен файл конфигурации (.cf). XML-выгрузку конфигурации этот шаг не принимает; "
            "вариант загрузки «конфигурация» в core-MCP — заглушка.",
        )
    if not infobase_exists(db_path):
        prepared = ensure_infobase(db_path, timeout=TIMEOUT_INFOBASE)
        if not prepared.get("success"):
            return prepared

    ib = find_ibcmd()
    if not ib.get("success"):
        return ib
    run = _run_ibcmd(ib["path"], ["config", "--db-path", db_path, "load",
                                  os.path.abspath(str(config_file))], timeout)
    state = read_state(db_path)
    state["config_file"] = os.path.abspath(str(config_file))
    if run["rc"] != 0:
        state["config_state"] = CONFIG_STATE_FAILED
        write_state(db_path, state)
        return _error(
            f"Не удалось загрузить конфигурацию в ИБ {db_path}: rc={run['rc']}",
            run["stderr"] or run["stdout"] or "ibcmd не сообщил причину",
        )
    state["config_state"] = CONFIG_STATE_LOADED
    state["config_loaded_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    write_state(db_path, state)
    return {"success": True, "db_path": db_path, "config_file": os.path.abspath(str(config_file)),
            "seconds": run["seconds"], "state": state}


def convert_and_load(binary_path, config_file=None, db_path=None, work_dir=None, force=False,
                     keep_layout=False, timeout=TIMEOUT_EXPORT):
    """Полный маршрут: `.erf`/`.epf` → каталог выгрузки → загрузка существующей точкой входа.

    Возвращает исход загрузки (его четыре статуса и карточка не меняются) плюс раздел
    `conversion` — отчёт о конвертации: путь и версия ibcmd, состояние ИБ, тайминги, число
    файлов содержимого, представление типов в разобранном XML. Разделение принципиальное:
    «не удалось сконвертировать» и «загрузчик отказал» — разные ответы (13.7, правило R13).

    Каталог разбора удаляется после УСПЕШНОЙ загрузки (keep_layout=False): при отказе он нужен
    оператору для разбора, и его путь печатается в подсказке.
    """
    binary_path = os.path.abspath(str(binary_path or ""))
    kind = BINARY_KINDS.get(os.path.splitext(binary_path)[1].lower())
    if not kind:
        return _stage(_error(
            f"Неизвестный вид файла: {binary_path or '(путь не задан)'}",
            "Ожидаются .erf (внешний отчёт) или .epf (внешняя обработка). Каталог выгрузки "
            "загружается load_1c_catalog_tool напрямую (правило R1).",
        ), "conversion")
    if not os.path.isfile(binary_path):
        return _stage(_error(f"Файл внешнего объекта не найден: {binary_path}",
                             "Проверьте путь: файл должен существовать на диске."), "conversion")

    work_dir = os.path.abspath(str(work_dir or DEFAULT_WORK_DIR))
    db_path = os.path.abspath(str(db_path or DEFAULT_DB_PATH))
    timings = {}

    ib = find_ibcmd()
    if not ib.get("success"):
        return _stage(ib, "conversion")

    prepared = ensure_infobase(db_path)
    if not prepared.get("success"):
        return _stage(prepared, "conversion")
    timings["infobase"] = prepared["seconds"]

    config_now = False
    if config_file:
        loaded = load_configuration(db_path, config_file)
        if not loaded.get("success"):
            return _stage(loaded, "conversion")
        timings["config_load"] = loaded["seconds"]
        config_now = True

    # Каталог разбора — свой на каждый файл: параллельные конвертации не перетирают друг друга.
    stamp = hashlib.sha1((binary_path + "|" + time.strftime("%Y%m%d%H")).encode("utf-8")).hexdigest()[:12]
    conv_dir = os.path.join(work_dir, "conv", stamp)
    exported = export_to_layout(binary_path, os.path.join(conv_dir, "object"), db_path,
                                timeout=timeout)
    if not exported.get("success"):
        return _stage(exported, "conversion")
    timings["export"] = exported["seconds"]

    # Состояние контекста называется ФАКТОМ разбора (13.7 п. 3): метка обёртки — только
    # способ не грузить конфигурацию повторно, а не источник истины об ИБ.
    config_note, state_after = _context_note(db_path, exported["type_names"], config_now)

    from config_load_router import load_catalog
    load_result = load_catalog(exported["layout_dir"], force=bool(force))
    answer = _merge_conversion(load_result, ib, binary_path, kind, db_path, prepared, config_now,
                              config_note, state_after, exported, timings, conv_dir, keep_layout)
    return answer


def _context_note(db_path, facts, config_now):
    """Назвать состояние контекста по разобранному XML и, если факт противоречит метке, снять метку.

    Три разных ответа — три разных смысла, смешивать их нельзя:
      * имена `cfg:` есть → контекст рабочий, состояние фиксируется фактом (метки до этого
        могло и не быть: ИБ создаётся и вне обёртки);
      * имён нет, есть `<v8:TypeId>`, а конфигурация в ИБ загружена (в этом вызове или раньше)
        → либо типов этого объекта в конфигурации нет, либо объект живёт на стандартных типах;
        это довод в пользу «объект вне конфигурации», но утверждает это только оператор (D4);
      * имён нет и конфигурация не загружена → типы не разрешены, и это дефект контекста.
    Ошибкой было бы смешать второе с третьим: сказать оператору «загрузите конфигурацию»,
    когда она уже загружена, — значит соврать про ИБ и увести в сторону от настоящего вывода.
    """
    if not facts.get("available"):
        return ("Не удалось прочитать разобранный XML для проверки типов: "
                + str(facts.get("reason")), configuration_state(db_path))

    if facts.get("types_resolved"):
        if configuration_state(db_path) != CONFIG_STATE_LOADED:
            state = read_state(db_path)
            state["config_state"] = CONFIG_STATE_LOADED
            state["config_source"] = "inferred_from_layout"
            write_state(db_path, state)
        return ("", CONFIG_STATE_LOADED)

    if config_now or configuration_state(db_path) == CONFIG_STATE_LOADED:
        return (
            "Конфигурация в ИБ загружена, но имён `cfg:` в разборе нет (cfg: — 0, "
            "<v8:TypeId> — %s): либо типов этого объекта в данной конфигурации нет, либо объект "
            "опирается на стандартные и примитивные типы, которые ibcmd отдаёт без ссылки на "
            "конфигурацию. Это довод в пользу того, что объект может не быть привязан к "
            "конфигурации, но утверждает привязку только оператор (правило D4)."
            % facts.get("type_id_elements"),
            CONFIG_STATE_LOADED,
        )
    return (
        "Типы реквизитов не разрешились: имён `cfg:` — 0, элементов `<v8:TypeId>` — %s. "
        "Конфигурация в ИБ не загружена: загрузите её параметром config_file=<путь к .cf>. "
        "Пустой тип реквизита при этом НЕ означает, что объект универсальный."
        % facts.get("type_id_elements"),
        configuration_state(db_path),
    )


def _merge_conversion(load_result, ib, binary_path, kind, db_path, prepared, config_now,
                      config_note, state_after, exported, timings, conv_dir, keep_layout):
    """Собрать ответ: карточка загрузки + отдельный раздел конвертации (правило R13)."""
    cleaned = False
    if load_result.get("success") and not keep_layout:
        try:
            shutil.rmtree(conv_dir, ignore_errors=True)
            cleaned = not os.path.exists(conv_dir)
        except OSError:
            cleaned = False

    conversion = {"ibcmd": ib["path"], "ibcmd_version": ib["version"], "binary": binary_path,
                  "object_kind": kind, "db_path": db_path,
                  "infobase_created": prepared.get("created", False),
                  "config_loaded_now": config_now,
                  "config_state_after": state_after,
                  "config_note": config_note,
                  "root_xml": exported["root_xml"], "content_files": exported["content_files"],
                  "type_names": exported["type_names"], "timings": timings,
                  "warnings": exported.get("warnings") or [],
                  "layout_removed": cleaned,
                  "layout_dir": None if cleaned else conv_dir}

    answer = dict(load_result)
    answer["conversion"] = conversion
    answer["stage"] = "load"
    if not cleaned:
        answer["layout_dir"] = conv_dir
        answer["hint"] = (str(answer.get("hint") or "") + " Каталог разбора сохранён: "
                          + conv_dir).strip()
    if not load_result.get("success"):
        answer["converted"] = True
    return answer
