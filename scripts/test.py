#!/usr/bin/env python3
"""Checks podrunner works in a cluster: args, secrets, connections (-- host:port ...), files coming back."""
import os
import platform
import socket
import sys
from datetime import datetime

SECRET_HINTS = ("PASS", "TOKEN", "SECRET", "KEY", "DSN", "CRED", "AUTH")

print(f"python:   {sys.version.split()[0]}")
print(f"platform: {platform.machine()}")
print(f"cwd:      {os.getcwd()}")
print(f"args:     {sys.argv[1:]}")

print(f"\nenv vars ({len(os.environ)}):")
for k in sorted(os.environ):
    v = "***" if any(s in k.upper() for s in SECRET_HINTS) else os.environ[k]
    print(f"  {k} = {v}")

failed = False
targets = [a for a in sys.argv[1:] if ":" in a]
if targets:
    print("\nconnections:")
for t in targets:
    host, _, port = t.rpartition(":")
    if not host or not port.isdigit():
        print(f"  FAIL {t}: not in host:port form")
        failed = True
        continue
    try:
        addrs = sorted({ai[4][0] for ai in socket.getaddrinfo(host, int(port), type=socket.SOCK_STREAM)})
    except socket.gaierror as e:
        print(f"  FAIL {t}: cannot resolve {host} ({e})")
        failed = True
        continue
    try:
        socket.create_connection((host, int(port)), timeout=5).close()
    except socket.timeout:
        print(f"  FAIL {t}: no answer in 5 s (usually a NetworkPolicy or firewall)")
        failed = True
        continue
    except OSError as e:
        print(f"  FAIL {t}: {e}")
        failed = True
        continue
    print(f"  ok   {t} ({', '.join(addrs)})")

with open("test.txt", "w") as f:
    f.write(f"OK at {datetime.now().isoformat()}\n")
    f.write(f"args: {sys.argv[1:]}\n")
print("\nwrote test.txt: it should come back in output/<pod>/")

sys.exit(1 if failed else 0)
