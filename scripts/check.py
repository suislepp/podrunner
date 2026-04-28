#!/usr/bin/env python3
"""Smoke test for podrunner: prints pod info, args, env vars, writes a test file.

Verifies:
- script copy+exec works (you see this output)
- workingDir is /work (cwd line)
- inner args pass through (args line)
- secrets injected as env vars (env vars list)
- file output works (check.txt creation; pass --output check.txt to copy back)
"""
import os
import sys
from datetime import datetime

SECRET_HINTS = ("PASSWORD", "TOKEN", "SECRET", "KEY")

print(f"python:  {sys.version.split()[0]}")
print(f"cwd:     {os.getcwd()}")
print(f"args:    {sys.argv[1:]}")
print()
print(f"env vars ({len(os.environ)} set):")
for k in sorted(os.environ):
    v = os.environ[k]
    if any(s in k.upper() for s in SECRET_HINTS):
        v = "***"
    print(f"  {k} = {v}")
print()

with open("check.txt", "w") as f:
    f.write(f"OK at {datetime.now().isoformat()}\n")
    f.write(f"args: {sys.argv[1:]}\n")
print("wrote check.txt — pass --output check.txt to copy it back")
