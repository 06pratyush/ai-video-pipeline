#!/usr/bin/env python3
import re, sys
raw = open(sys.argv[1], encoding="utf-8", errors="replace").read()
blocks = re.findall(r"```(?:[a-zA-Z0-9+#-]*)\n(.*?)```", raw, re.S)
out = blocks[0] if blocks else raw
open(sys.argv[2], "w", encoding="utf-8").write(out.rstrip() + "\n")
print(f"EXTRACTED_LINES={len(out.splitlines())} BLOCKS_FOUND={len(blocks)}")
