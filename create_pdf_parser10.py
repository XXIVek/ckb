# Часть 10 - блок main
lines = []
lines.append("")
lines.append("if __name__ == '__main__':")
lines.append('    examples = ["python pdf_parser.py PATH_TO_PDF"]')
lines.append("    if len(sys.argv) < 2:")
lines.append('        print("PDF Parser для документации по 1С")')
lines.append('        print("Использование:")')
lines.append('        for ex in examples:')
lines.append('            print(f"  {ex}")')
lines.append("        sys.exit(0)")
lines.append("    if '--list' in sys.argv:")
lines.append('        print("Примеры использования:")')
lines.append('        for ex in examples:')
lines.append('            print(f"  {ex}")')
lines.append("        sys.exit(0)")
lines.append("    pdf_file = sys.argv[1]")
lines.append("    if not Path(pdf_file).exists():")
lines.append('        print(f"Ошибка: файл не найден: {pdf_file}")')
lines.append("        sys.exit(1)")
lines.append("    result = parse_pdf_to_db(pdf_file)")
lines.append("    if result is None:")
lines.append("        sys.exit(1)")

with open(r"C:\1C_LLM\ckb\src\pdf_parser.py", "a", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("Часть 10 создана! Файл pdf_parser.py готов!")
