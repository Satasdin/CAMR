"""Build the standalone CAMR Personal executable for the current OS/CPU with PyInstaller.

    pip install pyinstaller numpy requests pyyaml pypdf sqlite-vec && pip install --no-deps -e .
    python packaging/build.py            # -> dist/camr-personal-<os>-<arch>.(zip|tar.gz)
"""

import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OS = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}[platform.system()]
ARCH = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}[platform.machine().lower()]
NAME = f"camr-personal-{OS}-{ARCH}"
SEP = ";" if OS == "windows" else ":"

args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--name", "camr-personal",
        "--add-data", f"{ROOT / 'camr' / 'app' / 'static'}{SEP}camr/app/static",
        "--collect-all", "sqlite_vec", "--hidden-import", "pypdf",
        "--exclude-module", "torch", "--exclude-module", "sentence_transformers", "--exclude-module", "streamlit",
        "--exclude-module", "matplotlib", "--exclude-module", "pandas", "--exclude-module", "anthropic",
        str(ROOT / "packaging" / "camr_personal.py")]
icon = ROOT / "packaging" / ("camr.ico" if OS == "windows" else "camr.icns")
if icon.exists() and OS != "linux":
    args[4:4] = ["--icon", str(icon)]
try:
    import sqlite_vec  # noqa: F401
except ImportError:  # no wheel for this platform (e.g. Windows on ARM): the store falls back to exact NumPy search
    args.remove("--collect-all"); args.remove("sqlite_vec")
subprocess.run(args, check=True, cwd=ROOT)

exe = ROOT / "dist" / ("camr-personal.exe" if OS == "windows" else "camr-personal")
stage = ROOT / "dist" / NAME
shutil.rmtree(stage, ignore_errors=True)
stage.mkdir(parents=True)
shutil.copy2(exe, stage / exe.name)
shutil.copy2(ROOT / "packaging" / "README.txt", stage / "README.txt")
shutil.copy2(ROOT / "LICENSE", stage / "LICENSE.txt")
if OS == "windows":
    out = ROOT / "dist" / f"{NAME}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in stage.iterdir():
            z.write(f, f"{NAME}/{f.name}")
else:
    out = ROOT / "dist" / f"{NAME}.tar.gz"
    with tarfile.open(out, "w:gz") as t:
        t.add(stage, arcname=NAME)
print(out)
