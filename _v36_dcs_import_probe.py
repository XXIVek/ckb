"""
_V36_DCS_IMPORT_PROBE — узел V36: добавляет ли импорт каталога метаданных НАШ макет СКД и
возвращает ли его содержимое обратно.

Что печатается (всё по факту прогона, захардкоженных чисел в скрипте нет):
  [0] фикстура MinCfg как есть: файлов, записей индекса в ConfigDumpInfo.xml, из них Template,
      объявления <Template> в XML объектов;
  [1] сценарий БЕЗ объявления: чистая ИБ -> `config load MinCfg.cf` -> `config export info`
      (базовый индекс) -> `config import <каталог, где файлы макета есть, а <Template> нет>`
      -> `config export info` -> разница записей индекса;
  [2] сценарий С объявлением в блоке объекта: в XML объекта вписано `<Template>МинМакет</Template>`
      перед закрывающим </ChildObjects> блока объекта (там же, где <Form>);
  [2b] сценарий с объявлением ВНУТРИ блока табличной части — так промахивается писатель обратных
      файлов; сценарий проверяет, заметит ли платформа ошибку размещения;
  [3] сверка сценариев: число новых записей индекса в каждом из них;
  [4] `config export objects DataProcessor.МинОбработка --recursive` -> сверка написанных файлов
      макета с выгруженными: статус СОВПАЛО / NORMALIZED (расходятся только строки, добавленные
      платформой) / DIFFERS / MISSING, плюс форма файла (BOM, переводы строк, размер).

Каждый сценарий берёт ЧИСТУЮ ИБ: второй импорт на той же ИБ увидел бы объект, созданный первым.

Вывод зонда (раздел 13.8 плана): импорт каталога метаданных добавляет в конфигурацию только
ОБЪЯВЛЕННЫЕ объекты — файлы каталога без объявления <Template> не дают ни одной записи индекса;
содержимое объявленного макета возвращается, но нормализованным: если в схеме нет варианта
настроек, платформа добавляет его сама.

Запуск: python _v36_dcs_import_probe.py [--keep]
Артефакты: _ibcmd_work/v36_probe/, _ibcmd_work/v36_probe/ib_no|ib_with
"""
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from ibcmd_bridge import (  # noqa: E402
    TIMEOUT_INFOBASE,
    TIMEOUT_LOAD_CONFIG,
    TIMEOUT_EXPORT,
    find_ibcmd,
    _run_ibcmd,
)

FIXTURE = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files\MinCfg")
FIXTURE_CF = Path(r"C:\1C_LLM\LoadDoc\Configurations\MinCfg_1Cv8.cf")
WORK = Path(r"C:\1C_LLM\ckb\_ibcmd_work\v36_probe")

OBJ_KIND_DIR = "DataProcessors"
OBJ_NAME = "МинОбработка"
TARGET = f"DataProcessor.{OBJ_NAME}"
TEMPLATE_NAME = "МинМакет"
# макет, который в фикстуре написала платформа (через Конфигуратор): он служит парой
# «наш файл» ↔ «файл платформы» в сверке round-trip
FIXTURE_TEMPLATE_NAME = "ОсновнаяСхемаКомпоновкиДанных"
# uuid нашего макета заявляет автор (у метаданных v4, п. 13.7); фиксированный — чтобы
# повторный прогон сравнивался с тем же значением
PROBE_UUID = "3f7a1c22-9d4e-4c7a-8b21-52f0a6c9d114"

# шапка файла регистрации берётся из фикстуры: набор пространств имён диктует платформа,
# выдумывать свой нельзя — берём заголовок файла, который она же и создала
FIXTURE_TEMPLATE_REG = (
    FIXTURE / OBJ_KIND_DIR / OBJ_NAME / "Templates" / f"{FIXTURE_TEMPLATE_NAME}.xml"
)

# макет, который пишем сами: минимальная СКД. default-namespace, как его пишет платформа
# (префикс dcscg: для того же URI импорт принимает, но выгрузка нормализует его в
# default-namespace — потому пишем сразу в той же форме)
DCS_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<DataCompositionSchema xmlns="http://v8.1c.ru/8.1/data-composition-system/schema"'
    ' xmlns:dcscom="http://v8.1c.ru/8.1/data-composition-system/common"'
    ' xmlns:dcscor="http://v8.1c.ru/8.1/data-composition-system/core"'
    ' xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings"'
    ' xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui"'
    ' xmlns:xs="http://www.w3.org/2001/XMLSchema"'
    ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
    '\t<dataSource>\n'
    '\t\t<name>ИсточникДанных1</name>\n'
    '\t\t<dataSourceType>Local</dataSourceType>\n'
    '\t</dataSource>\n'
    '\t<dataSet xsi:type="DataSetQuery">\n'
    '\t\t<name>НаборДанных1</name>\n'
    '\t\t<field xsi:type="DataSetFieldField">\n'
    '\t\t\t<dataPath>Наименование</dataPath>\n'
    '\t\t\t<field>Наименование</field>\n'
    '\t\t</field>\n'
    '\t\t<dataSource>ИсточникДанных1</dataSource>\n'
    '\t\t<query>ВЫБРАТЬ\n'
    '\tМинОбработка.Наименование КАК Наименование\n'
    'ИЗ\n'
    '\tМинОбработка.ТабличнаяЧасть1 КАК МинОбработка</query>\n'
    '\t</dataSet>\n'
    '</DataCompositionSchema>\n'
)



def run(ibcmd: str, args: list, timeout: int) -> dict:
    res = _run_ibcmd(ibcmd, args, timeout)
    tag = " ".join(args)
    if res["rc"] != 0:
        print(f"    rc={res['rc']} ({res['seconds']}с) err={res['stderr'][:500]}\n      :: {tag}")
    else:
        print(f"    ok {res['seconds']}с :: {tag}")
    return res


def out_dir(path: Path) -> str:
    """`--out` у `export info`/`export objects` — каталог, который ОБЯЗАН существовать:
    на несуществующем пути команда даёт «Каталог не обнаружен '<путь>\\ConfigDumpInfo.xml'», rc=-1."""
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def index_names(dump_root: Path):
    """имя -> id из ConfigDumpInfo.xml; None, если файла нет.
    `config export info --out=` принимает и файл, и каталог — поддерживаем оба варианта."""
    f = dump_root if dump_root.is_file() else dump_root / "ConfigDumpInfo.xml"
    if not f.is_file():
        return None
    text = f.read_text(encoding="utf-8-sig", errors="replace")
    return dict(re.findall(r'<Metadata\s+name="([^"]+)"\s+id="([^"]+)"', text))


def index_stats(label: str, idx: dict):
    tpl = sorted(n for n in idx if ".Template" in n)
    print(f"    {label}: записей {len(idx)}, Template-записей {len(tpl)}")
    for name in tpl:
        print(f"      {name} id={idx[name]}")


def add_template_files(root: Path):
    """пишем файлы макета: файл регистрации (шапка из фикстуры) + содержимое макета."""
    head = FIXTURE_TEMPLATE_REG.read_text(encoding="utf-8-sig").split("<Template uuid=")[0]
    reg = (
        head
        + f'<Template uuid="{PROBE_UUID}">\n'
        + "\t\t<Properties>\n"
        + f"\t\t\t<Name>{TEMPLATE_NAME}</Name>\n"
        + "\t\t\t<Synonym/>\n"
        + "\t\t\t<Comment/>\n"
        + "\t\t\t<TemplateType>DataCompositionSchema</TemplateType>\n"
        + "\t\t</Properties>\n"
        + "\t</Template>\n"
        + "</MetaDataObject>\n"
    )
    obj = root / OBJ_KIND_DIR / OBJ_NAME
    (obj / "Templates").mkdir(parents=True, exist_ok=True)
    (obj / "Templates" / f"{TEMPLATE_NAME}.xml").write_text(reg, encoding="utf-8")
    inner = obj / "Templates" / TEMPLATE_NAME / "Ext"
    inner.mkdir(parents=True, exist_ok=True)
    (inner / "Template.xml").write_text(DCS_XML, encoding="utf-8")


def add_template_declaration(root: Path, place: str = "object") -> str:
    """Вписывает <Template> в XML объекта.
    place="object"  — перед ПОСЛЕДНИМ </ChildObjects> файла: он закрывает блок объекта и идёт
                      после </TabularSection>. Именно там лежат <Form>/<Template> в выгрузке.
    place="tabular" — перед ПЕРВЫМ </ChildObjects>, то есть внутрь блока табличной части:
                      так промахивается писатель, и сценарь 3 проверяет, заметит ли это платформа."""
    f = root / OBJ_KIND_DIR / f"{OBJ_NAME}.xml"
    text = f.read_text(encoding="utf-8")
    decl = f"\t\t\t<Template>{TEMPLATE_NAME}</Template>\n"
    if f"<Template>{TEMPLATE_NAME}</Template>" in text:
        return decl.strip()
    j = text.index("</ChildObjects>") if place == "tabular" else text.rindex("</ChildObjects>")
    f.write_text(text[:j] + decl + text[j:], encoding="utf-8")
    return decl.strip()


def fixture_declarations() -> list:
    out = []
    for kind in ("Reports", "DataProcessors"):
        for p in sorted((FIXTURE / kind).glob("*.xml")):
            text = p.read_text(encoding="utf-8-sig", errors="replace")
            for m in re.finditer(r"<(Form|Template)>([^<]+)</\1>", text):
                out.append(f"{kind}/{p.name} -> {m.group(1)} {m.group(2)}")
    return out


def scenario(ibcmd: str, name: str, src: Path, title: str, place: str = ""):
    """один прогон на ЧИСТОЙ ИБ: load .cf -> базовый индекс -> import каталога -> новый индекс."""
    ib = WORK / f"ib_{name}"
    if ib.exists():
        shutil.rmtree(ib)
    print(f"\n[{title}] — ИБ {ib}")
    if run(ibcmd, ["infobase", "create", "--db-path", str(ib), "--create-database",
                   "--locale=ru"], TIMEOUT_INFOBASE)["rc"] != 0:
        return None
    run(ibcmd, ["config", "--db-path", str(ib), "load", str(FIXTURE_CF)], TIMEOUT_LOAD_CONFIG)
    info0 = WORK / f"info_{name}_0"
    run(ibcmd, ["config", "--db-path", str(ib), "export", "info",
                "--out", out_dir(info0)], TIMEOUT_EXPORT)
    base = index_names(info0)
    if base is None:
        print("    ОТКАЗ: после `config export info` нет ConfigDumpInfo.xml")
        return None
    index_stats("индекс ИБ после `config load` .cf", base)
    decl = add_template_declaration(src, place) if place else "не вписывалось"
    print(f"    объявление в XML объекта (блок {place or '—'}): {decl}")
    if place:
        tail = (src / OBJ_KIND_DIR / f"{OBJ_NAME}.xml").read_text(encoding="utf-8")[-200:]
        print("    хвост XML после правки: " + tail.replace("\n", " | "))
    run(ibcmd, ["config", "--db-path", str(ib), "import", str(src)], TIMEOUT_EXPORT)
    info1 = WORK / f"info_{name}_1"
    run(ibcmd, ["config", "--db-path", str(ib), "export", "info",
                "--out", out_dir(info1)], TIMEOUT_EXPORT)
    after = index_names(info1)
    if after is None:
        print("    ОТКАЗ: после импорта нет ConfigDumpInfo.xml")
        return None
    index_stats("индекс ИБ после `config import`", after)
    gained = sorted(set(after) - set(base))
    print(f"    новых записей относительно базового индекса: {len(gained)}")
    for n in gained:
        print(f"      + {n} id={after[n]}")
    return base, after, ib


def main() -> int:
    keep = "--keep" in sys.argv
    fails = []
    ib_info = find_ibcmd()
    if not ib_info.get("success"):
        print("ОТКАЗ:", ib_info.get("error"), ib_info.get("hint"))
        return 2
    ibcmd = ib_info["path"]
    print(f"ibcmd {ib_info['version']} — {ibcmd}")

    files = [p for p in FIXTURE.rglob("*") if p.is_file()]
    print(f"\n[0] фикстура {FIXTURE}")
    print(f"    файлов {len(files)}; {FIXTURE_CF.name} {FIXTURE_CF.stat().st_size} байт")
    index_stats("ConfigDumpInfo.xml фикстуры", index_names(FIXTURE) or {})
    for line in fixture_declarations():
        print(f"    объявление: {line}")

    if WORK.exists():
        shutil.rmtree(WORK)
    copies = {
        "no_decl": ("1. БЕЗ объявления макета", ""),
        "with_decl": ("2. С объявлением в блоке объекта", "object"),
        "wrong_place": ("3. С объявлением внутри блока табличной части", "tabular"),
    }
    for name in copies:
        shutil.copytree(FIXTURE, WORK / name)
        add_template_files(WORK / name)
    print(f"    наши файлы макета: {TEMPLATE_NAME}.xml, {TEMPLATE_NAME}/Ext/Template.xml"
          f" (uuid {PROBE_UUID})")

    results = {}
    for name, (title, place) in copies.items():
        got = scenario(ibcmd, name, WORK / name, title, place)
        if not got:
            return 2
        results[name] = got
    ib_with = results["with_decl"][2]

    gained = {n: sorted(set(r[1]) - set(r[0])) for n, r in results.items()}
    print("\n[3] сверка сценариев")
    for name, (title, _place) in copies.items():
        print(f"    {title}: новых записей {len(gained[name])}")
    for name in ("no_decl", "wrong_place"):
        if gained[name]:
            fails.append(f"{name}: макет появился без объявления в блоке объекта "
                         "— вывод 13.8 о роли объявления не подтвердился")
    want = {
        f"{TARGET}.Template.{TEMPLATE_NAME}": PROBE_UUID,
        f"{TARGET}.Template.{TEMPLATE_NAME}.Template": None,
    }
    after_yes = results["with_decl"][1]
    for name, uuid_expected in want.items():
        if name not in after_yes:
            fails.append(f"с объявлением — нет записи индекса {name}")
            continue
        if uuid_expected and after_yes[name].lower() != uuid_expected.lower():
            fails.append(f"uuid записи {name} не наш: {after_yes[name]}")

    print("\n[4] выгрузка объекта и сверка файлов макета")
    out = WORK / "objects"
    run(ibcmd, ["config", "--db-path", str(ib_with), "export", "objects", TARGET,
                "--recursive", "--out", out_dir(out)], TIMEOUT_EXPORT)
    with_decl = WORK / "with_decl"
    mine = with_decl / OBJ_KIND_DIR / OBJ_NAME / "Templates"
    rel = out / OBJ_KIND_DIR / OBJ_NAME / "Templates"
    fx_tpl = FIXTURE / OBJ_KIND_DIR / OBJ_NAME / "Templates"
    for label, src_path, got_path in (
        ("наш файл регистрации", mine / f"{TEMPLATE_NAME}.xml", rel / f"{TEMPLATE_NAME}.xml"),
        ("наше содержимое макета", mine / TEMPLATE_NAME / "Ext" / "Template.xml",
         rel / TEMPLATE_NAME / "Ext" / "Template.xml"),
        ("файл платформы: регистрация", fx_tpl / f"{FIXTURE_TEMPLATE_NAME}.xml",
         rel / f"{FIXTURE_TEMPLATE_NAME}.xml"),
        ("файл платформы: содержимое макета",
         fx_tpl / FIXTURE_TEMPLATE_NAME / "Ext" / "Template.xml",
         rel / FIXTURE_TEMPLATE_NAME / "Ext" / "Template.xml"),
    ):
        status, note, diff = compare_files(src_path, got_path)
        print(f"    {label}: {status} — {note}")
        if status != "MISSING":
            print(f"      написано: {file_shape(src_path)}; выгружено: {file_shape(got_path)}")
        for line in diff[:12]:
            print(f"      {line[:170]}")
        if status in ("DIFFERS", "MISSING"):
            fails.append(f"{label}: расхождение с написанным ({status})")

    print("\nитог:", "ПРОВАЛЕНО" if fails else "ПРОЙДЕНО")
    for item in fails:
        print("  -", item)
    if keep:
        print(f"артефакты оставлены: {WORK}")
    else:
        shutil.rmtree(WORK, ignore_errors=True)
    return 1 if fails else 0


def norm_lines(path: Path):
    """строки файла для сверки: BOM снят, CRLF → LF, завершающие пустые строки отброшены
    (платформа пишет файл без завершающего перевода строки)."""
    text = path.read_bytes().decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
    lines = text.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def file_shape(path: Path) -> str:
    """форма файла: BOM, переводы строк, размер — то, что обязан учитывать писатель обратных файлов."""
    raw = path.read_bytes()
    return (f"BOM={'есть' if raw[:3] == b'\xef\xbb\xbf' else 'нет'} "
            f"CRLF={'есть' if b'\r\n' in raw else 'нет'} {len(raw)} байт")


def compare_files(mine: Path, got: Path):
    """Возвращает (статус, пояснение, строки diff).
    СОВПАЛО — после нормализации байт-в-байт;
    NORMALIZED — расходятся только добавленные платформой строки варианта настроек;
    DIFFERS — любое другое расхождение; MISSING — файла нет."""
    if not got.is_file():
        return "MISSING", "файл не выгружен", []
    a, b = norm_lines(mine), norm_lines(got)
    if a == b:
        return "СОВПАЛО", f"{len(a)} строк побайтово после нормализации", []
    import difflib
    diff = list(difflib.unified_diff(a, b, "написано", "выгружено", lineterm="", n=0))
    added = [l[1:].strip() for l in diff if l.startswith("+") and not l.startswith("+++")]
    removed = [l[1:].strip() for l in diff if l.startswith("-") and not l.startswith("---")]
    if not removed and added and all(("settingsVariant" in l) or l.startswith("<dcsset:")
                                     for l in added):
        return ("NORMALIZED",
                f"платформа добавила {len(added)} строк варианта настроек "
                "(в написанном макете варианта не было); остальное побайтово совпало", diff)
    return ("DIFFERS", f"снято {len(removed)} строк, добавлено {len(added)}", diff)


if __name__ == "__main__":
    sys.exit(main())
