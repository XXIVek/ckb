import sys
sys.stdout.reconfigure(encoding="utf-8")
ls = open(r"C:\1C_LLM\ckb\src\mcp_tools_api.py", encoding="utf-8").read().split("\n")
a, b = int(sys.argv[1]), int(sys.argv[2])
for i in range(a - 1, min(b, len(ls))):
    print(f"{i+1}: {ls[i]}")
