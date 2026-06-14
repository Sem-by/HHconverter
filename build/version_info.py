"""Windows VERSION resource for PyInstaller (reduces SmartScreen/Defender false positives)."""

from __future__ import annotations

import re
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)


def _read_project_version(project_root: Path) -> str:
    init_py = project_root / "converter" / "__init__.py"
    if not init_py.is_file():
        return "0.1.0"
    for line in init_py.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "0.1.0"


def _version_tuple(version: str) -> tuple[int, int, int, int]:
    parts = [int(part) for part in re.findall(r"\d+", version)]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])  # type: ignore[return-value]


def build_version_info(project_root: Path) -> VSVersionInfo:
    version = _read_project_version(project_root)
    file_version = _version_tuple(version)

    return VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=file_version,
            prodvers=file_version,
            mask=0x3F,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0",
                        [
                            StringStruct("CompanyName", "HHConverter"),
                            StringStruct(
                                "FileDescription",
                                "Hand History Converter for Hand2Note",
                            ),
                            StringStruct("FileVersion", version),
                            StringStruct("InternalName", "HHConverter"),
                            StringStruct(
                                "LegalCopyright",
                                "Copyright (C) 2026 HHConverter",
                            ),
                            StringStruct("OriginalFilename", "HHConverter.exe"),
                            StringStruct("ProductName", "HHConverter"),
                            StringStruct("ProductVersion", version),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )
