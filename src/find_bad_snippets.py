#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Поиск плохих сниппетов (где answer - просто ссылка на файл)."""
import subprocess
import os

os.environ['PGPASSWORD'] = 'Sta090860'
os.environ['PGCLIENTENCODING'] = 'UTF8'

cmd = [
    r'C:\Postgres\bin\psql.exe', '-U', 'postgres', '-d', 'local_doc',
    '-h', 'localhost', '-tA', '-c',
    """SET client_encoding TO 'UTF8'; 
       SELECT id, question, left(answer, 200) as ans_preview 
       FROM knowledge_snippets 
       WHERE answer LIKE '%.md%' OR answer LIKE '%.html%' OR answer LIKE '%.pdf%'
          OR (answer LIKE 'C:\\%' AND length(answer) < 500)
          OR (answer LIKE '/docs/%' AND length(answer) < 200)
          OR (answer LIKE '/src/%' AND length(answer) < 200)
       ORDER BY id"""
]

proc = subprocess.run(cmd, capture_output=True, text=True, encoding='cp1251')
print(proc.stdout[:10000])
