import sys
from pathlib import Path

server_code = '''"""
MCP-сервер для 1C Knowledge Base.
Предоставляет инструменты для поиска и импорта документации по 1С:Предприятие.
"""

import sys as _sys
from pathlib import Path as _Path
from typing import Optional

_sys.path.insert(0, str(_Path(__file__).parent))

from fastmcp import FastMCP
from database import init_database
from search import (search_docs, search_fragments, get_doc, 
                    get_fragment_by_name, list_categories, get_import_log)
from importers import import_markdown_files, import_html_files


mcp = FastMCP(
    name="1c-knowledge-base",
    version="0.1.0",
    description="MCP-сервер для хранения и поиска документации по 1С:Предприятие"
)

'''

with open(r'C:\1C_LLM\ckb\src\server.py', 'w', encoding='utf-8') as f:
    f.write(server_code)
print("server.py part 1 created")
