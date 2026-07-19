#!/usr/bin/env python3
import os
import re

ROOT = os.path.dirname(os.path.dirname(__file__))
ENCODING_RE = re.compile(r"coding[:=]")

SKIP_DIRS = {"venv", ".venv", "__pycache__", ".git", "env", "node_modules"}

changed = 0
processed = 0

for dirpath, dirnames, filenames in os.walk(ROOT):
    parts = set(dirpath.split(os.sep))
    if parts & SKIP_DIRS:
        continue
    for fname in filenames:
        if not fname.endswith(".py"):
            continue
        path = os.path.join(dirpath, fname)
        processed += 1
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = []
        changed_file = False
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                if stripped.startswith("#!"):
                    new_lines.append(line)
                    continue
                if ENCODING_RE.search(line):
                    new_lines.append(line)
                    continue
                changed_file = True
                continue
            else:
                new_lines.append(line)
        if changed_file:
            bak = path + ".bak"
            if not os.path.exists(bak):
                try:
                    os.rename(path, bak)
                    with open(path, "w", encoding="utf-8") as f:
                        f.writelines(new_lines)
                except Exception:
                    with open(bak, "w", encoding="utf-8") as bf:
                        bf.writelines(lines)
                    with open(path, "w", encoding="utf-8") as f:
                        f.writelines(new_lines)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
            changed += 1

print(f"Processed {processed} .py files, modified {changed} files. Backups saved as .bak where changed.")
