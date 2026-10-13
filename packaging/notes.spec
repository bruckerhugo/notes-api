# PyInstaller spec for the standalone desktop app (one file; .app bundle on macOS).
# Build from the repository root: pyinstaller packaging/notes.spec
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 (SPECPATH is injected by PyInstaller)

hiddenimports = (
    collect_submodules("backend")  # imported lazily by desktop.embedded_server
    + collect_submodules("uvicorn")  # uvicorn loads its loop/protocol modules by name
    + ["sqlalchemy.dialects.sqlite"]
)

a = Analysis(
    [str(ROOT / "packaging" / "notes_app.py")],
    pathex=[str(ROOT)],
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "PySide6.QtWebEngineCore", "PySide6.QtQml"],
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="notes", console=False)
    coll = COLLECT(exe, a.binaries, a.datas, name="notes")
    app = BUNDLE(coll, name="Notes.app", bundle_identifier="io.github.bruckerhugo.notes")
else:
    # NOTES_CONSOLE_BUILD=1 builds a console variant, used to diagnose startup issues.
    console = os.environ.get("NOTES_CONSOLE_BUILD") == "1"
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, name="notes", console=console, upx=False
    )
