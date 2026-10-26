import sys, os; sys.path.insert(0, 'src')
from pathlib import Path
root = Path(r'C:\1C_LLM\LoadDoc\Configurations\XML_files\BGU2')
d = root / 'Catalogs' / 'ВариантыОтчетов' / 'Commands'
print('каталог команд:', d.exists())
if d.is_dir():
    for c in sorted(d.iterdir())[:6]:
        if c.is_dir():
            ext = c / 'Ext'
            print(' ', c.name, '| Ext:', ext.exists(), '| files:', [p.name for p in ext.iterdir()] if ext.is_dir() else '-')
