"""_v46b_shape_probe.py — состав сложных свойств подсистемы (Content/Picture/Explanation).

Читает два файла регистрации подсистем с непустыми Content/Picture и печатает
сами блоки как есть: по ним видно, чем заполнен Item (ссылка на объект метаданных
или группа) и что лежит в Ref картинки. Ничего не пишет, только печать.
"""
import pathlib
import re
import sys

BASE = pathlib.Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
CFGS = ("BP3", "BGU2", "KomMag", "MinCfg")


def block(text, start_tag):
    m = re.search(rf"<{start_tag}>.*?</{start_tag}>", text, re.S)
    return m.group(0) if m else f"<{start_tag}> — блок не найден"


def pick(cfg):
    """Первый файл подсистемы с непустым Content и, отдельно, первый с Picture/Ref."""
    root = BASE / cfg / "Subsystems"
    if not root.is_dir():
        return None, None
    content_hit = picture_hit = None
    for path in sorted(root.rglob("*.xml")):
        text = path.read_text(encoding="utf-8")
        if content_hit is None and re.search(r"<Content>\s*<", text):
            content_hit = (path, text)
        if picture_hit is None and re.search(r"<Picture[^>]*>\s*<(xr:)?Ref", text):
            picture_hit = (path, text)
        if content_hit and picture_hit:
            break
    return content_hit, picture_hit


def main():
    for cfg in CFGS:
        content_hit, picture_hit = pick(cfg)
        for label, hit in (("Content", content_hit), ("Picture", picture_hit)):
            if not hit:
                print(f"\n##### {cfg} / {label}: не найдено #####")
                continue
            path, text = hit
            print(f"\n########## {cfg} / {path.name} / {label} ##########")
            props = re.search(r"<Properties>.*?</Properties>", text, re.S)
            if label == "Content":
                print(block(text, "Content")[:2500])
            else:
                print(block(text, "Picture")[:1200])
                if props:
                    for tag in ("Explanation", "Synonym"):
                        m = re.search(rf"<{tag}>.*?</{tag}>", props.group(0), re.S)
                        if m and "<" in m.group(0)[len(tag) + 2:-len(tag) - 3]:
                            print(f"--- {tag} ---")
                            print(m.group(0)[:900])
            child = re.search(r"<ChildObjects>.*?</ChildObjects>", text, re.S)
            if child:
                print("--- ChildObjects (первые 800) ---")
                print(child.group(0)[:800])
    return 0


if __name__ == "__main__":
    sys.exit(main())
