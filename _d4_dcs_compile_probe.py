# -*- coding: utf-8 -*-
"""_d4_dcs_compile_probe.py — D-4: контекст конфигурации в сеансе и компиляция СКД при загрузке .erf.

Основание (факт 19.10.2026, _d1_erf_com_probe.txt). Путь ВнешниеОтчеты.Создать() рабочий
(пройден «Предупреждение безопасности»), падение — на компиляции макета:
  {(27,75)}: Неверные параметры "Перечисление.СтатусыРасходовУСН.НеСписаноНеОплачено"
  КОГДА ... = ЗНАЧЕНИЕ(<<?>>Перечисление.СтатусыРасходовУСН.НеСписаноНеОплачено)
Гипотеза «значения перечислений design-time недоступны» была проверена и ОТВЕРГНУТА прямо в тексте
ошибки: значения, которого в метаданных нет, платформа назвала бы «Значение перечисления не
найдено» (замер на MinCfg: «Значение перечисления "ВидыНоменклатуры.ТакогоЗначенияНет" не
найден», _d1_enum_probe.txt), а здесь нерезолвнут САМ тип — маркер <<?>> перед именем.

Основание (факт 20.10.2026, _d1_env_probe.txt). На ИБ _ibcmd_work/ib_bp3 пустой внешний отчёт
загружается, а оба отчёта сравнения падают на компиляции, и ошибки РАЗНЫЕ:
  базовый : {(27,75)} Неверные параметры "Перечисление.СтатусыРасходовУСН.НеСписаноНеОплачено"
  V26     : {(16,2)}  Таблица не найдена "РегистрНакопления.РасходыПриУСН.ОстаткиИОбороты"
в обеих строках стоит тот же маркер <<<?>>, то есть платформа не разрешает имена конфигурации;
там же Метаданные() сеанса не отдаются («Этот метод недоступен, так как объект не найден»), а
_d1_bp3_dcs_probe.txt на базе оператора дал «Член группы не найден».

Вопрос, который решает этот зонд: отказ относится к ПЛОЩАДКЕ (в сеансе нет конфигурации БП3)
или к СОДЕРЖИМОМУ файла. Ответ определяет, что чинить: контекст подключения или собранный XML.
Вывод формулируется по признакам, а не по памяти:
  - если в сеансе не разрешается ни одно имя метаданных БП3 (РегистрНакопления.РасходыПриУСН,
    Перечисление.СтатусыРасходовУСН) — виноват контекст: любой отчёт с таблицами конфигурации
    падал бы так же, и вывод про собранный файл делать нельзя;
  - если имена разрешаются, а загрузки разные — разница в содержимом файлов; тогда раздел [4]
    показывает, чем именно различаются тексты запросов в позициях, названных ошибками.

Что делает (одна итерация, только чтение):
  [1] поднимается к КАЖДОЙ из ИБ: база оператора (дана 20.10.2026 как площадка) и наша ИБ ibcmd.
      Каждая прогоняется целиком, а не «до первой успешной»: остановка на первой не давала сравнить
      площадки, тогда как регрессия исходной ошибки живёт именно в нашей ИБ после apply;
      время коннекта печатается;
  [2] отпечаток сеанса: имя и версия конфигурации, НайтиПоИмени() по именам из текстов ошибок,
      перечень значений Перечисление.СтатусыРасходовУСН (есть ли НеСписаноНеОплачено);
  [3] загрузка менеджером ВнешниеОтчеты четырёх файлов: пустой отчёт (управление — путь Создать()
      рабочий), базовый .erf, V26-файл, наш собранный (_v26_out/*.erf). Если отчёт загрузился —
      число наборов данных и параметров его схемы;
  [4] офлайн: нумерованные строки текста запроса обеих раскладок в позициях (27,75) и (16,2).

Запуск (обязательно с логом):
  python _d4_dcs_compile_probe.py --log _d4_dcs_compile_probe.txt
"""
import argparse
import gc
import os
import re
import sys
import time

sys.path.insert(0, r"C:\1C_LLM\ckb")
from _d1_erf_com_probe import (_log, count_of, first_attr, full, get,  # noqa: E402
                               iterate, make_protection, render, say, short)
import win32com.client  # noqa: E402

try:                                                        # вывод лога в консоль без cp1251
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:                                           # noqa: BLE001
    pass

# порядок: сначала площадка оператора (дана 19.10.2026 как рабочая), затем наша ИБ из ibcmd.
# способ подключения — V83.COMConnector (тот же, что у _d1_env_probe.py и _d1_bp3_dcs_probe.py)
IBS = [
    ("база оператора (площадка 19.10.2026)", 'File="C:\\1C_LLM\\Bases_Test\\BP3";Usr=admin;Pwd=;'),
    ("наша ИБ ibcmd (ibcmd config load BP3)", 'File="C:\\1C_LLM\\ckb\\_ibcmd_work\\ib_bp3";'),
]

# имена, названные в текстах обеих ошибок, + одно общее для проверки вида отпечатка
FIND_NAMES = [
    "РегистрНакопления.РасходыПриУСН",
    "Перечисление.СтатусыРасходовУСН",
    "РегистрНакопления.ПрочиеРасходы",
    "Справочник.Номенклатура",
]
ENUM_NAME = "Перечисление.СтатусыРасходовУСН"
ENUM_EXPECT = "НеСписаноНеОплачено"

# коллекции Метаданные по виду имени (русское и латинское имя свойства): через них
# имя вида и разрешается — НайтиПоИмени через IDispatch не отдаётся (замер D-7)
COLLECTION_PROPS = {
    "РегистрНакопления": ("РегистрыНакопления", "AccumulationRegisters"),
    "Перечисление": ("Перечисления", "Enums"),
    "Справочник": ("Справочники", "Catalogs"),
}

MANAGER_PROPS = ["ВнешниеОтчеты", "ExternalReports"]
ENUM_VALUES_PROPS = ["Значения", "Values"]

# порядок важен: сначала управление (пустой отчёт заведомо грузится), потом спорные файлы
ERFS = [
    ("управление: пустой отчёт", r"C:\1C_LLM\LoadDoc\Test3_ОтчетПустой.erf"),
    ("базовый (доставленный)", r"C:\1C_LLM\LoadDoc\БП3\СравнениеУСНИ90_2.erf"),
    ("V26 (редактированный)", r"C:\1C_LLM\LoadDoc\Edit_V26_СравнениеУСНИ90_2"
                             r"\СравнениеУСНИ90_2_v26.edited.erf"),
    ("наш собранный (_v26_out)", r"C:\1C_LLM\ckb\_v26_out\SpravkaKassaVed_202603.erf"),
]
SCHEMA_PROPS = ["СхемаКомпоновкиДанных", "DataCompositionSchema"]
DATASETS_PROPS = ["НаборыДанных", "DataSets"]
PARAMS_PROPS = ["Параметры", "Parameters"]
# имя загрузившегося отчёта: у внешнего отчёта через COM Имя/Name не отдаются
# (замер D-4c, строка 37: «AttributeError: <unknown>.Name»), а ИспользуемоеИмяФайла (52977) — да
REPORT_NAME_PROPS = ["Имя", "Name", "ИспользуемоеИмяФайла", "UsingFileName"]

# раздел [4]: раскладки, из которых брались тексты запросов, и позиции из текстов ошибок
LAYOUTS = [
    ("базовый", r"C:\1C_LLM\ckb\_v26_base\СравнениеУСНИ90_2\Макеты"
                r"\ОсновнаяСхемаКомпоновкиДанных\Ext\Template.xml", (27, 75)),
    ("V26", r"C:\1C_LLM\ckb\_v26_mine\СравнениеУСНИ90_2\Макеты"
            r"\ОсновнаяСхемаКомпоновкиДанных\Ext\Template.xml", (16, 2)),
]
QUERY_RE = re.compile(r"<query[^>]*>(.*?)</query>", re.S)
CDATA_RE = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.S)


def open_session(title, conn_str):
    """Сеанс по ОДНОЙ ИБ: (коннектор, сеанс, метаданные); метаданные могут быть None.

    Метаданные читаются СВОЙСТВОМ (замер 20.10.2026, _d9b_run.log): pywin32 CDispatch
    формально callable, поэтому прежний `value() if callable(value)` превращал рабочее
    значение в DISP_E_MEMBERNOTFOUND и ронял весь прогон (замер _d4b_run.log, строки 9-11).
    Явный вызов Метаданные() остаётся последней попыткой — только если свойство не далось.
    """
    say(f"\n[ИБ] {title}: {conn_str}")
    started = time.perf_counter()
    try:
        connector = win32com.client.Dispatch("V83.COMConnector")
        session = connector.Connect(conn_str)
    except Exception as exc:                                        # noqa: BLE001
        say(f"  сеанс не открыт ({short(exc)}) за "
            f"{time.perf_counter() - started:.1f} с")
        return None, None, None
    say(f"  сеанс открыт за {time.perf_counter() - started:.1f} с")
    for prop in ("ИмяБазы", "BaseName", "Конфигурация", "Configuration"):
        ok, value = get(session, prop)
        say(f"  сеанс.{prop} = {render(value) if ok else value}")
    ok, value = get(session, "Метаданные")
    meta = value if ok else None
    if not ok:
        say(f"  Метаданные как свойство: {value}")
        ok, value = get(session, "Metadata")
        if ok:
            meta = value
            say("  Метаданные получены через латинское имя Metadata")
    if meta is None:
        try:
            meta = session.Метаданные()                             # явный вызов метода
        except Exception as exc:                                    # noqa: BLE001
            say(f"  Метаданные() не отдаётся: {short(exc)}")
            meta = None
    if meta is not None:
        say("  Метаданные получены — конфигурация в сеансе есть")
    else:
        say("  Метаданные НЕ отдаются — конфигурации в сеансе нет; "
            "любой отчёт с таблицами конфигурации упадёт на компиляции")
    return connector, session, meta


def probe_ib(title, conn_str):
    """Полный прогон по одной ИБ: отпечаток сеанса + загрузка .erf.

    Возвращает (метаданные_получены, разрешено_имён, загружено_отчётов).
    """
    say("\n" + "=" * 72)
    say(f"СЕАНС: {title}")
    say("=" * 72)
    connector, session, meta = open_session(title, conn_str)
    if session is None:
        return False, 0, 0
    has_meta = meta is not None
    resolved, loaded = 0, 0
    try:
        if meta is not None:
            resolved = session_fingerprint(meta)
        loaded = load_reports(session) or 0
    finally:
        for closer in ("Закрыть", "Quit"):
            try:
                getattr(session, closer)()
            except Exception:                                       # noqa: BLE001
                pass
        try:
            connector.Disconnect()
        except Exception:                                           # noqa: BLE001
            pass
        # COM-ссылки снимаются до выхода процесса: живые ссылки дают 0xC0000005
        # на CoUninitialize (замер D-8)
        session = connector = meta = None
        gc.collect()
    # has_meta фиксируется ДО finally: там meta обнуляется, и прежний `return meta is not None`
    # (замер D-4c, строки 112-114) всегда давал «НЕ ПОЛУЧЕНЫ» при реально полученном сеансе
    return has_meta, resolved, loaded


def resolve_meta_name(meta, name):
    """(объект метаданных или None, канал разрешения).

    замер D-7 (_d7_run.log, строки 7, 25): метод `Метаданные.НайтиПоИмени` через
    IDispatch НЕ разрешается — GetIDsOfNames отказывает и по русскому, и по
    английскому имени. При этом коллекции Метаданные отдаются СВОЙСТВАМИ, поэтому
    имя вида разрешается ими: именованный доступ → метод поиска по имени у
    коллекции → обход коллекции по Имя.
    """
    kind, _, obj_name = name.partition(".")
    for cname in COLLECTION_PROPS.get(kind, ()):
        ok, coll = get(meta, cname)
        if not ok or coll is None:
            continue
        ok, item = get(coll, obj_name)
        if ok and item is not None:
            return item, f"{cname}.{obj_name}"
        for mname in ("НайтиПоИмени", "FindByName", "Get", "Получить"):
            try:
                item = getattr(coll, mname)(obj_name)
            except Exception:                                   # noqa: BLE001
                continue
            if item is not None:
                return item, f"{cname}.{mname}()"
        count = count_of(coll)
        items = iterate(coll)
        if items:
            for item in items:
                if item is None:
                    continue
                _, item_name = first_attr(item, ["Имя", "Name"])
                if item_name == obj_name:
                    shown = count if count is not None else len(items)
                    return item, f"обход {cname} ({shown} эл.) по Имя"
            return None, (f"коллекция {cname} получена ({len(items)} эл.), "
                          f"элемент с Имя={obj_name!r} не найден")
        if count is not None:
            return None, (f"коллекция {cname} получена ({count} эл.), "
                          "обход коллекции не отдаёт элементов")
        return None, f"коллекция {cname} получена, число элементов и обход не измеряются"
    return None, "коллекция вида не отдаётся ни через одно имя"


def session_fingerprint(meta):
    """Имя/версия конфигурации и разрешение имён из текстов ошибок — ответ на главный вопрос."""
    say("\n[2. ОТПЕЧАТОК СЕАНСА]")
    for prop in ("Имя", "Name", "Версия", "Version"):
        ok, value = get(meta, prop)
        if ok:
            say(f"  Метаданные.{prop} = {render(value)}")
    resolved = 0
    found_map = {}
    for name in FIND_NAMES:
        found, channel = resolve_meta_name(meta, name)
        if found is None:
            say(f"  НЕТ       {name} — {channel}")
            continue
        resolved += 1
        found_map[name] = found
        ok_name, found_name = first_attr(found, ["Имя", "Name"])
        say(f"  ЕСТЬ      {name} через {channel} -> "
            f"{render(found_name) if ok_name else render(found)}")
    say(f"  разрешилось имён: {resolved} из {len(FIND_NAMES)}")

    say(f"\n  значения {ENUM_NAME}:")
    enum = found_map.get(ENUM_NAME)
    if enum is None:
        enum, channel = resolve_meta_name(meta, ENUM_NAME)
        if enum is None:
            say(f"    отказ: {channel}")
            return resolved
    ok, coll = first_attr(enum, ENUM_VALUES_PROPS)
    if not ok or coll is None or isinstance(coll, str):
        # замер D-4c (два прогона): `Значения`/`Values` у объекта перечисления через COM
        # внешнего соединения НЕ отдаётся («AttributeError: <unknown>.Values»). Прежний код
        # звал iterate() по этому тексту ошибки и печатал 32 «значения» — посимвольный
        # разбор сообщения, а не состав перечисления.
        say(f"    Значения перечисления через COM не отдаются: {coll}")
        say("    состав значений этим каналом не измеряется; на вывод о компиляции СКД "
            "это не влияет — она подтверждена загрузкой отчёта в разделе [3]")
        return resolved
    names = []
    for item in iterate(coll):
        if isinstance(item, str):
            names.append(item)
            continue
        ok_name, value_name = first_attr(item, ["Имя", "Name"])
        names.append(value_name if ok_name and isinstance(value_name, str) else render(item))
    say(f"    значений {len(names)}: {', '.join(names)}")
    say(f"    {ENUM_EXPECT}: {'ЕСТЬ' if ENUM_EXPECT in names else 'НЕТ'}")
    return resolved


def dump_schema(report):
    """Число наборов данных и параметров схемы загрузившегося отчёта."""
    name, schema = first_attr(report, SCHEMA_PROPS)
    if schema is None:
        say("    схема не отдаётся ни через одно имя; пробую ПолучитьМакет")
        for template_name in ("ОсновнаяСхемаКомпоновкиДанных", "СхемаКомпоновкиДанных"):
            try:
                candidate = report.ПолучитьМакет(template_name)
            except Exception:                                       # noqa: BLE001
                continue
            if candidate is None:
                continue
            ok, _ = get(candidate, "Параметры")
            if ok:
                schema, name = candidate, f"ПолучитьМакет({template_name})"
                break
        if schema is None:
            return
    say(f"    схема получена через {name}")
    for props in (DATASETS_PROPS, PARAMS_PROPS):
        pname, coll = first_attr(schema, props)
        if coll is None:
            say(f"    {props[0]}: не отдаётся ({coll})")
            continue
        say(f"    {props[0]} (через {pname}): {len(iterate(coll))}")


def load_reports(session):
    say("\n[3. ЗАГРУЗКА .erf МЕНЕДЖЕРОМ ВнешниеОтчеты]")
    mname, manager = first_attr(session, MANAGER_PROPS)
    if manager is None:
        say(f"  менеджер не получен: {manager}")
        return
    say(f"  менеджер получен через {mname}")
    protection, ctor = make_protection(session)
    if protection is None:
        say("  без описания защиты предупреждение безопасности блокирует Создать")
        return
    loaded = 0
    for title, path in ERFS:
        say(f"\n  --- {title}: {path}")
        if not os.path.exists(path):
            say("    файла нет")
            continue
        try:
            report = manager.Создать(path, False, protection)
        except Exception as exc:                                    # noqa: BLE001
            say(f"    ОТКАЗ Создать(файл, Ложь, {ctor}): {full(exc)[:900]}")
            continue
        if report is None:
            say("    Создать() вернул None")
            continue
        loaded += 1
        ok_rn, rname = first_attr(report, REPORT_NAME_PROPS)
        say(f"    ЗАГРУЖЕН через {mname}.Создать(файл, Ложь, {ctor}): "
            f"{render(rname) if ok_rn else os.path.basename(path)}")
        dump_schema(report)
    say(f"\n  загрузилось отчётов: {loaded} из {len(ERFS)}")
    return loaded


def query_text(path):
    """Строки первого текста <query> раскладки (CDATA разобран) — для сверки с позицией ошибки."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    match = QUERY_RE.search(text)
    if match is None:
        return None
    body = match.group(1)
    cdata = CDATA_RE.search(body)
    return (cdata.group(1) if cdata else body).replace("\r\n", "\n").split("\n")


def show_query_positions():
    say("\n[4. ТЕКСТ ЗАПРОСА В ПОЗИЦИЯХ ОШИБОК (офлайн, без COM)]")
    for title, path, (line, column) in LAYOUTS:
        say(f"\n  --- {title}: {path}")
        lines = query_text(path)
        if lines is None:
            say("    текста <query> в раскладке нет (файл недоступен или другой формат)")
            continue
        say(f"    строк текста запроса: {len(lines)}")
        start = max(0, line - 4)
        end = min(len(lines), line + 2)
        for index in range(start, end):
            number = index + 1
            say(f"    {number:>3} | {lines[index][:160]}")
            if number == line:
                say(f"         {' ' * (column - 1)}^ позиция ошибки")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default=r"C:\1C_LLM\ckb\_d4_dcs_compile_probe.txt")
    args = parser.parse_args()

    say("D-4: контекст конфигурации сеанса и компиляция СКД при загрузке .erf")
    # каждая ИБ прогоняется целиком: прежнее «остановиться на первой успешной» не давало
    # сравнить площадки, а регрессия исходной ошибки относится именно к нашей ИБ (после apply)
    results = []
    for title, conn_str in IBS:
        has_meta, resolved, loaded = probe_ib(title, conn_str)
        results.append((title, has_meta, resolved, loaded))
    say("\n[ИТОГ ПО ПЛОЩАДКАМ]")
    got = 0
    for title, has_meta, resolved, loaded in results:
        if has_meta:
            got += 1
            say(f"  МЕТАДАННЫЕ ПОЛУЧЕНЫ — {title}: разрешено имён {resolved} "
                f"из {len(FIND_NAMES)}, загружено отчётов {loaded} из {len(ERFS)}")
        else:
            say(f"  МЕТАДАННЫЕ НЕ ПОЛУЧЕНЫ — {title}")
    say(f"  Метаданные отдали ИБ: {got} из {len(IBS)}")
    if got == 0:
        say("  ни одна ИБ не отдала Метаданные(): контекста конфигурации нет ни на одной "
            "площадке — вывод о содержимом файла делать нельзя.")
    show_query_positions()
    say("\n=D-4 завершена=")

    with open(args.log, "w", encoding="utf-8") as fh:
        fh.write("\n".join(_log) + "\n")
    print(f"\nлог: {args.log} ({len(_log)} строк)")


if __name__ == "__main__":
    main()


