from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

DropboxMode = Literal["original", "none"]
_DROPBOX_MODES: frozenset[str] = frozenset({"original", "none"})
SOURCE_HERO_TOKEN = "Hero"


@dataclass(frozen=True, slots=True)
class Settings:
    import_path: Path
    export_path: Path
    dropbox_base_path: Path
    chico_import_path: Path | None
    dropbox_mode: DropboxMode

    player_alias: str
    clear_import_after_convert: bool
    coin_as_ps: bool


def program_base() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def assets_dir() -> Path:
    if getattr(sys, "frozen", False):
        return bundle_dir() / "converter" / "assets"
    return Path(__file__).resolve().parent / "assets"


def default_settings() -> Settings:
    base = program_base()
    return Settings(
        import_path=base / "import",
        export_path=base / "export",
        dropbox_base_path=Path(),
        chico_import_path=None,
        dropbox_mode="none",
        player_alias="Hero",
        clear_import_after_convert=False,
        coin_as_ps=True,
    )


def is_path_set(path: Path) -> bool:
    text = str(path).strip().replace("\\", "/")
    return bool(text) and text not in {".", ""}


def path_display(path: Path) -> str:
    if not is_path_set(path):
        return ""
    return _path_str(path)


def ensure_default_config(config_path: Path) -> None:
    if config_path.is_file():
        return

    settings = default_settings()
    save_settings(config_path, settings)
    settings.import_path.mkdir(parents=True, exist_ok=True)
    settings.export_path.mkdir(parents=True, exist_ok=True)


def load_settings(config_path: Path) -> Settings:
    data = _read_json(config_path)
    chico_raw = data.get("chico_import_path")
    dropbox_mode = str(data.get("dropbox_mode", "none"))
    if dropbox_mode == "converted":
        dropbox_mode = "original"
    if dropbox_mode not in _DROPBOX_MODES:
        raise ValueError(
            f"Invalid dropbox_mode {dropbox_mode!r}; expected one of: original, none"
        )

    return Settings(
        import_path=_path_from_config(data["import_path"]),
        export_path=_path_from_config(data["export_path"]),
        dropbox_base_path=_path_from_config(data.get("dropbox_base_path", "")),
        chico_import_path=Path(chico_raw) if chico_raw else None,
        dropbox_mode=dropbox_mode,  # type: ignore[arg-type]
        player_alias=str(data["player_alias"]),
        clear_import_after_convert=bool(data.get("clear_import_after_convert", False)),
        coin_as_ps=bool(data.get("coin_as_ps", True)),
    )


def default_config_path() -> Path:
    return program_base() / "config.json"


def save_settings(config_path: Path, settings: Settings) -> None:
    if config_path.is_file():
        data = _read_json(config_path)
    else:
        data = {}

    data["import_path"] = _path_str(settings.import_path)
    data["export_path"] = _path_str(settings.export_path)
    data["dropbox_base_path"] = _path_str(settings.dropbox_base_path)
    data["chico_import_path"] = (
        _path_str(settings.chico_import_path) if settings.chico_import_path else None
    )
    data["dropbox_mode"] = settings.dropbox_mode
    data["player_alias"] = settings.player_alias
    data["clear_import_after_convert"] = settings.clear_import_after_convert
    data["coin_as_ps"] = settings.coin_as_ps
    data.pop("room_seat_tokens", None)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def _path_from_config(value: Any) -> Path:
    if value is None or value == "":
        return Path()
    path = Path(str(value))
    if path.is_absolute():
        return path
    return program_base() / path


def _path_str(path: Path) -> str:
    if not is_path_set(path):
        return ""
    try:
        return path.resolve().relative_to(program_base().resolve()).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path} ({exc}). "
            "Windows paths must use forward slashes (C:/folder/file) "
            "or escaped backslashes (C:\\\\folder\\\\file)."
        ) from exc
