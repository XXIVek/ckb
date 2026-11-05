import os
root = r'C:\1C_LLM\LoadDoc\Configurations\XML_files'

def show(cfg, name, chars=400):
    p = os.path.join(root, cfg, 'Ext', name)
    if not os.path.exists(p):
        print('MISSING', cfg, name); return
    b = open(p, 'rb').read()
    t = b.decode('utf-8-sig', 'replace')
    print('=== %s / %s bytes=%d chars=%d' % (cfg, name, len(b), len(t)))
    print(t[:chars].replace('\r', '\\r').replace('\n', '\\n'))
    print('--- tail:', t[-120:].replace('\r', '\\r').replace('\n', '\\n'))
    for kw in ('Справочник', 'Документ', 'РегистрСведений', 'Перечисление'):
        print('   kw %-16s %d' % (kw, t.count(kw)))

show('KomMag', 'ParentConfigurations.bin', 200)
show('BGU2', 'ParentConfigurations.bin', 200)
show('BP3', 'MobileClientSignature.bin', 300)
show('UT11', 'StandaloneConfigurationContent.bin', 300)
