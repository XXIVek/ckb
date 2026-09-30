#!/usr/bin/env python3
import json
with open(r'C:\Users\Buh\.cline\data\settings\cline_mcp_settings.json') as f:
    d = json.load(f)
print('Серверов:', len(d['mcpServers']))
for k, v in d['mcpServers'].items():
    disabled = v.get('disabled', False)
    print(f'  {k}: disabled={disabled}')
