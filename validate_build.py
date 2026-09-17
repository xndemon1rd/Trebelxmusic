"""Offline release validator for TrebelxMusic. Exits non-zero on real defects."""
from __future__ import annotations
import ast, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
errors=[]; warnings=[]
required=["Dockerfile","requirements.txt","config.py","start","TrabelxMusic","strings"]
for name in required:
    if not (ROOT/name).exists(): errors.append(f"missing required path: {name}")
for p in ROOT.rglob("*.py"):
    if "__pycache__" in p.parts: continue
    try: ast.parse(p.read_text(encoding="utf-8", errors="replace"), filename=str(p))
    except SyntaxError as e: errors.append(f"syntax: {p.relative_to(ROOT)}:{e.lineno}:{e.offset}: {e.msg}")
# Bare except blocks hide unexpected programming/runtime failures.
bare_except=[]
for p in ROOT.rglob("*.py"):
    if "__pycache__" in p.parts: continue
    for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if line.strip() == "except:": bare_except.append(f"{p.relative_to(ROOT)}:{i}")
if bare_except: errors.append("bare except found: " + ", ".join(bare_except[:20]))
# Downloader safety checks: cookie-capable YouTube fallbacks must not silently
# discard the configured cookie jar, and a clean client fallback must exist.
downloader = ROOT / "TrabelxMusic/utils/downloader.py"
if downloader.exists():
    dtext = downloader.read_text(encoding="utf-8", errors="replace")
    if 'opts.pop("cookiefile", None)' in dtext:
        errors.append("YouTube fallback removes configured cookiefile")
    help_file = ROOT / "TrabelxMusic/plugins/bot/help.py"
    if help_file.exists():
        htext = help_file.read_text(encoding="utf-8", errors="replace")
        if "COMMAND_PAGE_COUNT" in htext and "from TrabelxMusic.utils.command_catalog import COMMAND_PAGE_COUNT" not in htext:
            errors.append("help.py uses COMMAND_PAGE_COUNT without importing it")
    for marker in ("mweb-cookie", "tv-cookie", "android_vr-clean", "cookie_file_status"):
        if marker not in dtext:
            errors.append(f"downloader robustness marker missing: {marker}")

# Legacy quote= is allowed only when the compatibility shim exists.
quote_files=[]
for p in ROOT.rglob("*.py"):
    if "__pycache__" in p.parts: continue
    txt=p.read_text(encoding="utf-8", errors="replace")
    if re.search(r"\bquote\s*=", txt) and p.name != "bot.py": quote_files.append(p)
if quote_files and not (ROOT/"TrabelxMusic/core/bot.py").exists(): errors.append("legacy quote= calls found without compatibility shim")
req=(ROOT/"requirements.txt").read_text(encoding="utf-8", errors="replace")
for dep in ("pymongo","urllib3"):
    if not re.search(rf"(?im)^{re.escape(dep)}(?:[<>=!~\[]|$)", req): warnings.append(f"direct import dependency not declared: {dep}")
gitignore=(ROOT/".gitignore").read_text(encoding="utf-8", errors="replace")
for secret in (".env","*.session","TrabelxMusic/assets/cookies.txt"):
    if secret not in gitignore: errors.append(f"secret/runtime path not ignored: {secret}")
print(f"VALIDATION: {len(errors)} error(s), {len(warnings)} warning(s)")
for x in errors: print("ERROR:",x)
for x in warnings: print("WARNING:",x)
sys.exit(1 if errors else 0)
