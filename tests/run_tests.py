"""Runs every test file in this folder and prints a summary.  python tests/run_tests.py  [name filter]

The tests use made-up hand landmarks (no camera, no hand model) and fake Windows mouse / camera / window
objects, so they run in seconds on any OS. test_loop_* drive the real main loop with fakes; on Windows they
may briefly show a tray icon. A test prints PASS/FAIL lines and stops at the first FAIL (assert)."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
flt = sys.argv[1] if len(sys.argv) > 1 else ""
files = sorted(f for f in os.listdir(HERE) if f.startswith("test_") and f.endswith(".py") and flt in f)
bad = []
for f in files:
    r = subprocess.run([sys.executable, os.path.join(HERE, f)], capture_output=True, text=True, timeout=900, cwd=HERE)
    out = r.stdout + r.stderr
    fails = [l for l in out.splitlines() if l.startswith("FAIL")]
    ok = r.returncode == 0 and not fails
    n = sum(1 for l in out.splitlines() if l.startswith("PASS"))
    print(f"{'ok  ' if ok else 'FAIL'} {f:32s} {n:3d} checks passed" + ("" if ok else f"  <- {fails[:1] or out.strip().splitlines()[-1:]}"))
    if not ok:
        bad.append(f)
print(f"\n{len(files) - len(bad)}/{len(files)} test files passed")
sys.exit(1 if bad else 0)
