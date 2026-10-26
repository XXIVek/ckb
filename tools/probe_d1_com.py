#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/probe_d1_com.py — D1: подставляет ли СКД DesignTimeValue параметра, снятого вариантом.

Вопрос (docs/EXTERNAL_OBJECT_EDIT_PLAN.md, раздел «D1 без живой ИБ», оставшаяся открытая часть):
значения параметрам ОтражениеВУСН, СтатусыОплатыРасходовУСН, Сч41 объявляет сама схема
(templates.ext: <value xsi:type="dcscor:DesignTimeValue"> + useRestriction=true), а вариант
настроек «Основной» снимает их использование (<dcscor:use>false</dcscor:use> + value=nil).
По сохранённому содержимому нельзя ответить, что с этим делает СКД в запросе НаборДанных1:
подставляет объявленное схемой значение в критерии функции регистра или отдаёт параметр
неопределённым. Отсюда и пауза: правку use=true вносить нельзя, пока неясно, что она меняет.

Что делает зонд — три независимых наблюдения, каждое со своим исходом:
  L1  состояние параметров в КомпоновщикНастроек.Настройки.ПараметрыДании загруженного .erf
      (Имя / Использование / Значение) — то, с чем отчёт работает, если код ничего не меняет;
  L2  фактические параметры источников данных в МАКЕТЕ компоновки: вызов
      Новый КомпоновщикМакетаКомпоновкиДанных -> Выполнить(Схема, Настройки, ДанныеРасшифровки),
      т.е. ровно тот, что делает модуль объекта (config_snippet 1578 «Сформировать»);
  L3  только с --run: выполнение ПроцессорКомпоновкиДанных и число выгруженных строк
      (внешние наборы данных при этом пустые — наблюдение деградирует, а не падает).

Транспорт — COM-коннектор V83.COMConnector (in-process, та же сборка платформы, что и ibcmd,
работающий с ИБ _ibcmd_work/ib_bp3): Connect(СтрокаСоединения) -> ВнешниеОтчеты.Загрузить(файл).
Имена API перебираются в обеих записях (русской и английской), потому что набор доступных имён
зависит от языка сборки; недополученное имя называется прямо, а не молча.

Чего зонд НЕ доказывает:
  * он не трогает состояние поддержки и не правит объект: замер читает, а не измеряет правку;
  * L3 не является доказательством по реальным данным БП3 (демо-данные регистра РасходыПриУСН
    могут быть пусты) — он нужен только чтобы показать, что запрос набора данных выполняется;
  * вывод относится к этой конфигурации (БП3) и этой версии платформы; версия называется в ответе.

Результат — вердикт по каждой из трёх целей: applied (значение из схемы дошло до запроса),
not_applied (не дошло), undetermined (измерение не состоялось). Вердикт любого содержания —
это результат замера, а не ошибка скрипта (та же граница, что в probe_external_processing_properties:
ОТКЛОНЕНИЕ это результат). Код возврата 1 — только если измерение не состоялось вовсе
(нет COM-класса, нет ИБ, не удалось подключиться, не удалось загрузить отчёт).

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/probe_d1_com.py [--run] [--skip-db] [--erf <файл>] [--ib <каталог>]
                                 [--uuid <uuid объекта>] [--usr <имя>] [--pwd <пароль>]
"""

import argparse
import json
import re
import sys
import types
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

try:  # кириллица в консоли Windows (cp1251) — как в остальных валидаторах
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PASSED, FAILED, WARNINGS = [], [], []


def check(title, ok, detail=""):
    (PASSED if ok else FAILED).append(title)
    print(f"[{'OK  ' if ok else 'FAIL'}] {title}")
    if detail:
        for line in str(detail).splitlines():
            print(f"       {line}")


def warn(title, detail=""):
    WARNINGS.append(title)
    print(f"[WARN] {title}")
    if detail:
        for line in str(detail).splitlines():
            print(f"       {line}")


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# ----------------------------------------------------------------------------- объекты замера
ERF_DEFAULT = r"C:\1C_LLM\LoadDoc\БП3\СравнениеУСНИ90_2.erf"
IB_DEFAULT = str(ROOT / "_ibcmd_work" / "ib_bp3")
OBJECT_UUID_DEFAULT = "a6db7252-5cfd-4e33-8e28-66e8f1a74a46"
OBJECT_NAME_DEFAULT = "СравнениеУСНИ90_2"
TEMPLATE_DEFAULT = "ОсновнаяСхемаКомпоновкиДанных"
# Цели D1 — ИМЕНА параметров в схеме (не имена их типов): СтатусыОплатыРасходовУСН — это имя
# параметра, его тип — Перечисление.СтатусыРасходовУСН (замер templates.ext, строки 698—753).
TARGETS = ("ОтражениеВУСН", "СтатусыОплатыРасходовУСН", "Сч41")

# ----------------------------------------------------------------------- COM-слой
GUID_RE = re.compile(r"^\{[0-9A-Fa-f-]{36}\}$")


def reg_default(*parts):
    """Значение по умолчанию ключа HKCR ('' — если ключа или значения нет).

    Пусто — это отсутствие факта, а не факт отсутствия регистрации: HKCR объединяет
    HKCU\\Software\\Classes и HKLM\\Software\\Classes, и запись в одном из них может
    просто не содержать нужного значения.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "\\".join(parts)) as key:
            return (winreg.QueryValue(key, "") or "").strip()
    except OSError:
        return ""


def reg_value(key_path, value_name):
    """Именованное значение ключа HKCR ('' — если ключа или значения нет).

    Значение и ключ — разные вещи: `ThreadingModel` лежит значением в
    `CLSID\\{...}\\InprocServer32`, а не отдельным подключом.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key_path) as key:
            return str(winreg.QueryValueEx(key, value_name)[0] or "").strip()
    except OSError:
        return ""


def resolve_clsids(prog_id):
    """CLSID, под которыми зарегистрирован ProgID, в порядке COM-активатора.

    Замер 19.10.2026: 1С кладёт CLSID в подключ `V83.COMConnector\\CLSID`, а значение
    по умолчанию самого ключа ProgID — это ОПИСАНИЕ класса («1CV83 COM Connector Class»),
    причём в HKCU ключ затенён именно описанием, без подключения CLSID. Прежняя реализация читала
    значение по умолчанию ключа ProgID и принимала описание за CLSID, из-за чего живой
    замер падал с «V83.COMConnector не зарегистрирован», хотя Dispatch работает.
    Порядок: `ProgID\\CLSID`, затем значение по умолчанию, если оно похоже на GUID,
    затем цель из `CurVer` (у 1С есть `V83.COMConnector.1`).
    """
    found, seen = [], {prog_id}

    def harvest(name):
        if not name or name in seen:
            return
        seen.add(name)
        for value in (reg_default(name, "CLSID"), reg_default(name)):
            if GUID_RE.match(value) and value not in found:
                found.append(value)

    harvest(prog_id)
    harvest(reg_default(prog_id, "CurVer"))
    return found


def com_class_info(prog_id="V83.COMConnector"):
    """Справка о зарегистрированном COM-классе: CLSID, InprocServer32, версия из пути.

    Нужно называть прямо: in-process активация безопасна только тогда, когда сборка
    comcntr.dll та же, что у ibcmd, работающего с этой ИБ. Разные сборки — другое
    измерение, и скрывать это нельзя. ThreadingModel печатается потому, что он решает,
    безопасна ли активация в этом процессе (замер: Both).
    """
    info = {"prog_id": prog_id, "clsid": "", "dll": "", "version": "",
            "threading_model": "", "error": ""}
    clsids = resolve_clsids(prog_id)
    if not clsids:
        info["error"] = (f"{prog_id}: CLSID не найден ни в подключе CLSID, ни в значении "
                         "по умолчанию, ни через CurVer (регистрации нет либо она затенена)")
        return info
    for clsid in clsids:
        dll = reg_default("CLSID", clsid, "InprocServer32")
        if not dll:
            continue
        info["clsid"] = clsid
        info["dll"] = dll
        info["threading_model"] = reg_value(f"CLSID\\{clsid}\\InprocServer32",
                                           "ThreadingModel")
        found = re.findall(r"\d+\.\d+\.\d+\.\d+", dll)
        info["version"] = found[0] if found else ""
        return info
    info["clsid"] = clsids[0]
    info["error"] = (f"CLSID {', '.join(clsids)} найден, но InprocServer32 не заполнен "
                     "ни у одного из них")
    return info


def clip(text, limit):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + "…"


def error_text(exc):
    """Однострочный текст ошибки COM (в многострочном выводе тонет причина)."""
    return " ".join(str(exc).split())


def pick(obj, *names):
    """Первое доступное СВОЙСТВО объекта (русскую или английскую запись имени).

    Возвращает (значение, использованное имя) или (None, ""). Имена перебираются потому,
    что набор доступных имён COM-коннектора зависит от языка сборки; недополученное имя
    называется в ответе, а не подменяется догадкой.

    Замер 19.10.2026 (`_d1_names_probe.py`): у сеанса есть `ВнешниеОтчеты` и
    `ExternalReports`, а запись через «ё» (`ВнешниеОтчёты`) отвечает AttributeError —
    поэтому обе записи держим в кандидатах, но факт именно такой. Прежняя реализация
    отбрасывала значение по признаку `callable(value)`, и это ломало весь слой наблюдений:
    pywin32 отвечает на любое имя динамического диспетчера объектом `CDispatch`, а он
    вызывает `__call__`, то есть `callable()` истинно у ВСЕХ вложенных объектов. Теперь
    отбрасываются только настоящие Python-функции/методы.
    """
    for name in names:
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        if isinstance(value, (types.BuiltinFunctionType, types.MethodType,
                              types.FunctionType)):
            continue
        return value, name
    return None, ""


def call_method(obj, names, *args):
    """Вызвать первый доступный метод из перечня имён. Возвращает (результат, имя, ошибки).

    Третьим возвращается НЕ последняя ошибка, а все попытки. Прежняя реализация отдавала
    `last_error`, и отказ первого имени терялся: живой отказ `Загрузить` (19.10.2026)
    был подписан текстом второй попытки — `<unknown>.Load`, то есть ответ называл не ту
    причину. строка ошибок читается `error_text`'ом как есть.
    """
    errors = []
    for name in names:
        try:
            fn = getattr(obj, name)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}/getattr: {error_text(exc)}")
            continue
        try:
            return fn(*args), name, ""
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}/call: {error_text(exc)}")
    return None, "", "; ".join(errors)


def com_session(ib_path, usr="", pwd=""):
    r"""Открывает COM-сессию живой ИБ через V83.COMConnector (in-process).

    Возвращает (сеанс, причину отказа). Строка соединения — файловая ИБ, той же формы,
    что принимает `ibcmd --db-path`. Usr/Pwd подставляются только если переданы: у части
    баз вход без пользователя невозможен (замер 19.10.2026: C:\1C_LLM\Bases_Test\BP3
    требует Usr=admin, C:\1C_LLM\ckb\_ibcmd_work\ib_bp3 — нет).

    Сеанс не закрывается: у объекта сеанса коннектора нет ни Close, ни Закрыть (замер
    того же дня: AttributeError на оба имени), поэтому процесс завершается вместе со
    скриптом — это ограничение транспорта, а не потерянная очистка.
    """
    try:
        import win32com.client
    except ImportError as exc:
        return None, f"pywin32 не установлен: {exc}"
    try:
        connector = win32com.client.Dispatch("V83.COMConnector")
    except Exception as exc:  # noqa: BLE001
        return None, f"Dispatch V83.COMConnector не выполнен: {error_text(exc)}"
    conn_string = f'File="{ib_path}";'
    if usr:
        conn_string += f"Usr={usr};Pwd={pwd};"
    try:
        session = connector.Connect(conn_string)
    except Exception as exc:  # noqa: BLE001
        return None, f"Connect не выполнен: {error_text(exc)}"
    if session is None:
        return None, "Connect вернул пустой сеанс"
    return session, ""


def coll_count(coll):
    for name in ("Количество", "Count"):
        try:
            return int(getattr(coll, name))
        except Exception:
            continue
    return None


def coll_items(coll):
    """Элементы BSL-коллекции через COM: Количество + Элемент(i), иначе Элементы/Items."""
    for container_name in ("Элементы", "Items"):
        try:
            inner = getattr(coll, container_name)
            if coll_count(inner) is not None:
                coll = inner
                break
        except Exception:
            pass
    count = coll_count(coll)
    if count is None:
        return []
    items = []
    for index in range(count):
        value, _, _ = call_method(coll, ("Элемент", "Element"), index)
        if value is not None:
            items.append(value)
    return items


def find_by_name(container, key):
    """Найти элемент коллекции/соответствия по имени. Возвращает (значение, способ).

    Порядок: штатный поиск (Получить/Get/НайтиПоИмени/FindByName), затем обход со сравнением
    имени элемента. Второй путь нужен потому, что у части коллекций метода поиска нет, а
    соответствие через Элемент(i) вообще не перебирается.
    """
    if container is None:
        return None, ""
    value, used, _ = call_method(container, ("Получить", "Get", "НайтиПоИмени", "FindByName"), key)
    if value is not None:
        return value, used
    for item in coll_items(container):
        name, _ = pick(item, "Имя", "Name")
        if name is not None and str(name) == str(key):
            return item, "обход"
    return None, ""


def new_object(conn, type_name):
    return call_method(conn, ("NewObject", "СоздатьОбъект"), type_name)


VALUE_TYPES = (str, int, float, bool, bytes)
CONTAINER_MARKERS = ("массив", "array", "список", "list", "соответствие", "map", "структура")


def describe(conn, value, depth=0):
    """Описание значения 1С: имя типа, внутренняя строка, внешнее представление.

    Ничего не додумывает: если конкретная функция глобального контекста не получена, в
    описании остаётся поле err с текстом отказа, и вердикт по такому параметру будет
    undetermined, а не «значения нет».
    """
    if value is None:
        return {"kind": "none", "text": ""}
    if isinstance(value, VALUE_TYPES):
        return {"kind": "primitive", "type_name": type(value).__name__,
                "text": str(value), "internal": str(value), "external": str(value), "err": []}
    described = {"kind": "v8object", "type_name": "", "internal": "", "external": "", "err": []}
    type_value, _, exc = call_method(conn, ("ТипЗначения", "TypeValue"), value)
    if type_value is not None:
        described["type_name"], _ = pick(type_value, "ИмяТипа", "TypeName")
    else:
        described["err"].append("ТипЗначения: " + error_text(exc))
    for names, key in ((("ЗначениеВСтрокуВнутр", "ValueToStringInternal"), "internal"),
                       (("ПолучитьВнешнееПредставление", "GetExternalPresentation"), "external")):
        got, _, exc = call_method(conn, names, value)
        if got is not None:
            described[key] = str(got)
        else:
            described["err"].append(names[0] + ": " + error_text(exc))
    lowered = (described["type_name"] or "").lower()
    described["items"] = []
    if depth < 2 and any(marker in lowered for marker in CONTAINER_MARKERS):
        described["items"] = [describe(conn, item, depth + 1)
                              for item in coll_items(value)]
    described["text"] = " | ".join(part for part in
                                   (described["external"], described["internal"]) if part)
    return described


def describe_line(conn, described):
    """Строка описания уже разобранного значения (чтобы не звать платформу повторно)."""
    if described["kind"] == "none":
        return "не задано (None)"
    parts = []
    if described.get("type_name"):
        parts.append("тип=" + str(described["type_name"]))
    if described.get("external"):
        parts.append("представление=" + clip(described["external"], 160))
    if described.get("internal"):
        parts.append("внутр=" + clip(described["internal"], 200))
    for item in described.get("items") or []:
        parts.append("элемент: " + describe_line(conn, item))
    if described.get("err"):
        parts.append("не получено: " + "; ".join(clip(e, 120) for e in described["err"]))
    return "; ".join(parts) if parts else described["kind"]


# ---------------------------------------------------------------- ожидания схемы (из БД)
def design_time_expectations(uuid, template_name):
    """Что объявляет схема по каждому параметру: DesignTimeValue и состояние из варианта.

    Источник — сохранённый templates.ext через src/enrichment_dcs (тот же разбор, что у
    get_config_template_tool). Сравнение поведения СКД с текстом схемы возможно только против
    того же разбора, а не против второй реализации: иначе расхождение нашлось бы в парсерах.
    """
    import enrichment_dcs

    answer = enrichment_dcs.get_template_content(uuid=uuid, name=template_name)
    if not answer.get("success"):
        return {}, answer.get("error") or "разбор макета не выполнен"
    entry = answer.get("dcs_entry") or {}
    if not entry.get("parsed"):
        return {}, entry.get("reason") or "содержимое макета не разобрано"
    expected = {}
    for param in entry.get("parameters") or []:
        name = str(param.get("name") or "").strip()
        if not name:
            continue
        design = [str(item.get("text") or "").strip()
                  for item in param.get("values") or []
                  if "DesignTimeValue" in str(item.get("type") or "")
                  and str(item.get("text") or "").strip()]
        uses = [str(item.get("use") or "").strip().lower()
                for item in param.get("settings_usage") or []]
        expected[name] = {
            "design_values": design,
            "tokens": design_tokens(design),
            "variant_use": ("false" if "false" in uses else
                            ("true" if "true" in uses else "")),
            "value_type": param.get("value_type") or [],
            "use_restriction": str(param.get("use_restriction") or ""),
        }
    return expected, ""


def design_tokens(design_values):
    """Токены, по которым значение из XML опознаётся в представлении значения 1С.

    DesignTimeValue пишется полным именем (Перечисление.ОтражениеВУСН.Принимаются), а
    представление значения в платформе — именем значения (Принимаются). Берутся оба варианта:
    совпадение по любому из них и называется в ответе.
    """
    tokens = set()
    for text in design_values:
        tokens.add(text.strip().lower())
        tail = text.split(".")[-1].strip().lower()
        if tail:
            tokens.add(tail)
    return sorted(tokens, key=len, reverse=True)


def matched_tokens(described, tokens):
    haystack = " ".join(filter(None, [described.get("text", ""),
                                      str(described.get("type_name", ""))])).lower()
    for item in described.get("items") or []:
        haystack += " " + (item.get("text") or "").lower()
    return [token for token in tokens if token and token in haystack]


# ----------------------------------------------------------------------- наблюдения (COM)
def param_rows(conn, parameters, marker):
    """Прочитать коллекцию параметров (настроек или макета): имя, использование, значение.

    Значение параметра настроек — ValueItem: сам объект значения не даёт, значение лежит
    во внутреннем Значение. Поэтому читается и внешний объект, и внутренний; если
    внутреннего нет, описывается внешний — иначе «значение есть» и «значения нет»
    неразличимы.
    """
    rows = []
    if parameters is None:
        print(f"  {marker}: коллекции нет")
        return rows
    for item in coll_items(parameters):
        name, _ = pick(item, "Имя", "Name")
        if name is None:
            continue
        use_value, _ = pick(item, "Использование", "Use")
        value, _ = pick(item, "Значение", "Value")
        inner, _ = pick(value, "Значение", "Value") if value is not None else (None, "")
        described = describe(conn, inner if inner is not None else value)
        row = {"name": str(name),
               "use": "" if use_value is None else str(use_value),
               "described": described}
        rows.append(row)
        print(f"  {marker} | {row['name']} | use={row['use'] or '?'} | "
              f"{describe_line(conn, described)}")
    if not rows:
        print(f"  {marker}: коллекция пуста или не разобрана")
    return rows


def get_prop(obj, marker, *names):
    value, used = pick(obj, *names)
    if value is None:
        print(f"  {marker}: имя из {list(names)} не получено")
    return value


def load_report(session, path):
    """Загрузить .erf штатным средством: ВнешниеОтчеты.Загрузить(файл)."""
    manager, _ = pick(session, "ВнешниеОтчеты", "ExternalReports")
    if manager is None:
        return None, "у сеанса нет ВнешниеОтчеты / ExternalReports"
    report, used, exc = call_method(manager, ("Загрузить", "Load"), str(path))
    if report is None:
        return None, f"Загрузить не выполнен: {error_text(exc)}"
    return report, used


def get_schema(report, template_name):
    """Схема компоновки данных: свойство отчёта, иначе макет с той же схемой."""
    schema, _ = pick(report, "ОсновнаяСхемаКомпоновкиДанных", "DataCompositionMainSchema")
    if schema is not None:
        return schema, "ОсновнаяСхемаКомпоновкиДанных"
    layout_template, _, exc = call_method(report, ("ПолучитьМакет", "GetLayout"),
                                          str(template_name))
    if layout_template is not None:
        schema, _ = pick(layout_template, "СхемаКомпоновкиДанных", "DataCompositionSchema")
        if schema is not None:
            return schema, f"ПолучитьМакет({template_name}).СхемаКомпоновкиДанных"
    return None, error_text(exc)


def observe_l1(conn, report):
    """L1: параметры в КомпоновщикНастроек.Настройки — с чем отчёт работает «как есть»."""
    section("L1: параметры настроек загруженного объекта отчёта")
    composer = get_prop(report, "L1", "КомпоновщикНастроек", "SettingsComposer")
    if composer is None:
        return []
    settings = get_prop(composer, "L1", "Настройки", "Settings")
    if settings is None:
        return []
    return param_rows(conn, get_prop(settings, "L1", "Параметры", "Parameters"), "PARAM")


def observe_l2(conn, report, schema, settings):
    """L2: параметры в МАКЕТЕ компоновки после КомпоновщикМакета.Выполнить.

    Это и есть ответ на вопрос D1: дошло ли объявленное схемой значение до выражений,
    которые исполняет запрос набора данных.
    """
    section("L2: параметры макета компоновки (КомпоновщикМакета.Выполнить)")
    compositor, used, exc = new_object(conn, "КомпоновщикМакетаКомпоновкиДанных")
    if compositor is None:
        compositor, used, exc = new_object(conn, "DataCompositionLayoutCompositor")
    if compositor is None:
        print(f"  L2: компоновщик макета не создан: {error_text(exc)}")
        return []
    print(f"  L2: компоновщик макета создан через {used}")
    layout, used, exc = call_method(compositor, ("Выполнить", "Compose"), schema, settings)
    if layout is None:
        print(f"  L2: Выполнить(схема, настройки) не выполнен: {error_text(exc)}")
        return []
    print(f"  L2: макет получен через {used}")
    return param_rows(conn, get_prop(layout, "L2", "Параметры", "Parameters"),
                      "LAYOUT_PARAM")


def observe_l3(conn, schema, settings):
    """L3: полный цикл до выгрузки строк. Показывает только что запрос выполняется."""
    section("L3: выполнение компоновки (ПроцессорКомпоновки.Выполнить)")
    data_parameters = get_prop(schema, "L3", "ПараметрыДанных", "DataParameters")
    processor, used, exc = new_object(conn, "ПроцессорКомпоновкиДанных")
    if processor is None:
        processor, used, exc = new_object(conn, "DataCompositionProcessor")
    if processor is None:
        print(f"  L3: процессор компоновки не создан: {error_text(exc)}")
        return None
    result, used, exc = call_method(processor, ("Выполнить", "Compose"),
                                   settings, data_parameters)
    if result is None:
        print(f"  L3: Выполнить не удался: {error_text(exc)}")
        return None
    rows, used, exc = call_method(result, ("Выгрузить", "Result"))
    count = coll_count(rows) if rows is not None else None
    if count is None:
        print(f"  L3: Выгрузить не отдаёт количество: {error_text(exc)}")
        return None
    print(f"  RESULT_ROWS | {count}")
    return count


def judge(targets, expected, l1_rows, l2_rows, conn, expectation_error=""):
    """Вердикт по каждой цели: applied / not_applied / undetermined.

    Критерий один: у параметра, которому вариант снимает использование, в макете
    компоновки есть значение, совпадающее с DesignTimeValue из схемы, — значит значение
    подставляется, и правка запроса без правки значений невозможна (applied). Значения
    нет — параметр уходит в запрос неопределённым (not_applied). Остальное —
    undetermined: измерение не состоялось или сравнение не определено.
    """
    verdicts = {}
    for name in targets:
        expectation = expected.get(name) or {}
        tokens = expectation.get("tokens") or []
        l1 = next((r for r in l1_rows if r["name"] == name), None)
        l2 = next((r for r in l2_rows if r["name"] == name), None)
        facts = []
        if l1 is not None:
            facts.append("L1 use=" + (l1["use"] or "?") + " " +
                         describe_line(conn, l1["described"]))
        if l2 is not None:
            facts.append("L2 use=" + (l2["use"] or "?") + " " +
                         describe_line(conn, l2["described"]))
        if expectation_error:
            verdicts[name] = ("undetermined",
                              "ожидания схемы не прочитаны: " + expectation_error, facts)
            continue
        if name not in expected:
            verdicts[name] = ("undetermined",
                              "параметра нет в разборе схемы макета — сравнивать не с чем",
                              facts)
            continue
        if not tokens:
            verdicts[name] = ("undetermined",
                              "в схеме нет DesignTimeValue по этому параметру — "
                              "сравнивать не с чем", facts)
            continue
        if l2 is None:
            verdicts[name] = ("undetermined",
                              "параметр не найден в макете компоновки", facts)
            continue
        matched = matched_tokens(l2["described"], tokens)
        if matched:
            verdicts[name] = ("applied",
                              "значение DesignTimeValue дошло до макета: " +
                              ", ".join(matched), facts)
        elif l2["described"]["kind"] == "none":
            verdicts[name] = ("not_applied",
                              "в макете значения нет — DesignTimeValue не подставляется",
                              facts)
        else:
            verdicts[name] = ("undetermined",
                              "значение есть, но оно не совпадает с DesignTimeValue "
                              "из схемы", facts)
    return verdicts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--erf", default=ERF_DEFAULT)
    parser.add_argument("--ib", default=IB_DEFAULT)
    parser.add_argument("--uuid", default=OBJECT_UUID_DEFAULT)
    parser.add_argument("--template", default=TEMPLATE_DEFAULT)
    parser.add_argument("--usr", default="")
    parser.add_argument("--pwd", default="")
    parser.add_argument("--run", action="store_true",
                        help="добавить L3: выполнение компоновки и число строк выгрузки")
    parser.add_argument("--skip-db", action="store_true",
                        help="не читать ожидания схемы из сохранённого templates.ext")
    parser.add_argument("--json", default="")
    args = parser.parse_args()

    section("ТРАНСПОРТ И ОБЪЕКТ ЗАМЕРА")
    info = com_class_info()
    if info["error"]:
        print(f"  Отказ: {info['error']}")
        return 1
    print(f"  OK | COM | {info['prog_id']} | CLSID {info['clsid']} | "
          f"ThreadingModel {info['threading_model'] or '?'} | "
          f"версия {info['version'] or '?'} | {info['dll']}")
    erf_path = Path(args.erf)
    ib_path = Path(args.ib)
    if not erf_path.exists():
        print(f"  Отказ: файла отчёта нет: {erf_path}")
        return 1
    if not ib_path.exists():
        print(f"  Отказ: каталога информационной базы нет: {ib_path}")
        return 1
    session, reason = com_session(str(ib_path), args.usr, args.pwd)
    if session is None:
        print(f"  Отказ: {reason}")
        return 1
    print(f"  OK | IB | {ib_path}")

    expected, expectation_error = {}, ""
    if not args.skip_db:
        expected, expectation_error = design_time_expectations(args.uuid, args.template)
        if expectation_error:
            print(f"  Ожидания схемы не прочитаны: {expectation_error}")
        else:
            print(f"  OK | SCHEMA-EXPECT | параметров в разборе макета: {len(expected)}")

    report, used = load_report(session, str(erf_path))
    if report is None:
        print(f"  Отказ: {used}")
        return 1
    print(f"  OK | REPORT | {erf_path.name} | загружен через {used}")
    schema, how = get_schema(report, args.template)
    if schema is None:
        print(f"  Отказ: схема компоновки не получена: {how}")
        return 1
    print(f"  OK | SCHEMA | получена через {how}")

    settings = get_prop(schema, "SCHEMA", "Настройки", "Settings")
    targets = list(TARGETS)

    l1_rows = observe_l1(session, report)
    l2_rows = observe_l2(session, report, schema, settings)
    rows = observe_l3(session, schema, settings) if args.run else None
    if not args.run:
        print("\n  L3 пропущен (запуск с --run добавляет выполнение компоновки)")

    verdicts = judge(targets, expected, l1_rows, l2_rows, session, expectation_error)
    section("ВЕРДИКТ D1: подставляет ли СКД DesignTimeValue параметров, "
            "использование которых снимает вариант настроек")
    for name in targets:
        verdict, reason, facts = verdicts[name]
        declared = expected.get(name) or {}
        print(f"  {verdict.upper()} | PARAM | {name}")
        print("      ожидание схемы: " +
              (" | ".join(declared.get("design_values") or []) or "не прочитано"))
        if declared:
            print("      в варианте: use=" + (declared.get("variant_use") or "?") +
                  " | useRestriction=" + (declared.get("use_restriction") or "?") +
                  " | тип=" + (",".join(declared.get("value_type") or []) or "?"))
        for fact in facts:
            print(f"      {fact}")
        print(f"      вывод: {reason}")

    counts = {"applied": 0, "not_applied": 0, "undetermined": 0}
    for verdict, _, _ in verdicts.values():
        counts[verdict] += 1
    overall = "D1 CONFIRMED" if counts["applied"] else (
        "D1 REFUTED" if counts["not_applied"] and not counts["undetermined"]
        else "D1 UNDETERMINED")
    print(f"\n  ИТОГ | {overall} | applied={counts['applied']} "
          f"not_applied={counts['not_applied']} undetermined={counts['undetermined']}")

    if args.json:
        payload = {
            "ib": str(ib_path),
            "erf": str(erf_path),
            "uuid": args.uuid,
            "template": args.template,
            "com": {k: info[k] for k in ("prog_id", "dll", "version", "clsid",
                                         "threading_model")},
            "expectation_error": expectation_error,
            "result_rows": rows,
            "counts": counts,
            "verdict": overall,
            "targets": {name: {
                "design_values": (expected.get(name) or {}).get("design_values") or [],
                "tokens": (expected.get(name) or {}).get("tokens") or [],
                "variant_use": (expected.get(name) or {}).get("variant_use") or "",
                "verdict": verdicts[name][0],
                "reason": verdicts[name][1],
                "facts": verdicts[name][2]}
                for name in targets},
        }
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        print(f"  JSON | {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

