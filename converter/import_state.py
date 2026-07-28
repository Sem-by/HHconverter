from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

from converter.settings import program_base


def import_state_path() -> Path:
    return program_base() / "_internal" / "import_watch_state.json"


@dataclass(frozen=True, slots=True)
class FileFingerprint:
    name: str
    size: int
    mtime_ns: int

    @classmethod
    def from_path(cls, path: Path, *, root: Path | None = None) -> FileFingerprint:
        st = path.stat()
        if root is not None:
            try:
                name = path.relative_to(root).as_posix()
            except ValueError:
                name = path.name
        else:
            name = path.name
        return cls(name=name, size=st.st_size, mtime_ns=st.st_mtime_ns)

    def key(self) -> str:
        return f"{self.name}|{self.size}|{self.mtime_ns}"

    @property
    def basename(self) -> str:
        return Path(self.name).name


@dataclass
class FolderWatchState:
    processed_keys: set[str]
    freshest_mtime_ns: int

    def to_json(self) -> dict[str, Any]:
        return {
            "processed_keys": sorted(self.processed_keys),
            "freshest_mtime_ns": self.freshest_mtime_ns,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any] | None) -> FolderWatchState:
        if not data:
            return cls(processed_keys=set(), freshest_mtime_ns=0)
        keys = {str(k) for k in data.get("processed_keys", [])}
        freshest = int(data.get("freshest_mtime_ns", 0) or 0)
        return cls(processed_keys=keys, freshest_mtime_ns=freshest)


@dataclass
class ImportWatchStore:
    """Persisted folder-watch fingerprints plus first-run date for Downloads."""

    folders: dict[str, FolderWatchState]
    first_run_date: date

    def to_json(self) -> dict[str, Any]:
        return {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "first_run_date": self.first_run_date.isoformat(),
            "folders": {k: v.to_json() for k, v in self.folders.items()},
        }


def load_watch_store() -> ImportWatchStore:
    path = import_state_path()
    today = date.today()
    if not path.is_file():
        return ImportWatchStore(folders={}, first_run_date=today)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ImportWatchStore(folders={}, first_run_date=today)

    folders_raw = raw.get("folders", {})
    folders = {str(k): FolderWatchState.from_json(v) for k, v in folders_raw.items()}
    first = _parse_first_run_date(raw.get("first_run_date"), fallback=today)
    return ImportWatchStore(folders=folders, first_run_date=first)


def save_watch_store(store: ImportWatchStore) -> None:
    path = import_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store.to_json(), indent=2) + "\n", encoding="utf-8")


def load_watch_state() -> dict[str, FolderWatchState]:
    """Backward-compatible helper — prefer load_watch_store()."""
    return load_watch_store().folders


def save_watch_state(state: dict[str, FolderWatchState]) -> None:
    """Preserve first_run_date when only folder fingerprints change."""
    store = load_watch_store()
    store.folders = state
    save_watch_store(store)


def first_run_min_mtime_ns(first_run: date) -> int:
    """Earliest mtime (ns) accepted for Downloads auto-import (local midnight)."""
    # Naive datetime.timestamp() is interpreted as local time on Windows/POSIX.
    start = datetime.combine(first_run, time.min)
    return int(start.timestamp() * 1_000_000_000)


def folder_key(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def select_new_files(
    folder: Path,
    state: FolderWatchState,
    *,
    suffixes: tuple[str, ...] = (".txt", ".zip"),
    recursive: bool = False,
    min_mtime_ns: int | None = None,
) -> list[Path]:
    """Return files in folder that look new vs stored fingerprints / freshest mtime.

    When ``min_mtime_ns`` is set (Downloads first-run gate), files older than that
    timestamp are ignored entirely — not imported and not marked processed.
    """
    if not folder.is_dir():
        return []

    if recursive:
        candidates = sorted(
            p
            for p in folder.rglob("*")
            if p.is_file() and p.suffix.lower() in suffixes
        )
    else:
        candidates = sorted(
            p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in suffixes
        )
    out: list[Path] = []
    for path in candidates:
        fp = FileFingerprint.from_path(path, root=folder if recursive else None)
        if min_mtime_ns is not None and fp.mtime_ns < min_mtime_ns:
            continue
        if fp.key() in state.processed_keys:
            continue
        if state.freshest_mtime_ns and fp.mtime_ns < state.freshest_mtime_ns:
            # Match legacy basename keys and recursive relative-path keys.
            name_seen = any(
                k.startswith(f"{fp.name}|")
                or k.startswith(f"{fp.basename}|")
                or k.split("|", 1)[0].endswith(fp.basename)
                for k in state.processed_keys
            )
            if name_seen:
                continue
        out.append(path)
    return out


def mark_processed(
    state: FolderWatchState,
    paths: list[Path],
    *,
    root: Path | None = None,
) -> FolderWatchState:
    keys = set(state.processed_keys)
    freshest = state.freshest_mtime_ns
    for path in paths:
        if not path.is_file():
            continue
        fp = FileFingerprint.from_path(path, root=root)
        keys.add(fp.key())
        freshest = max(freshest, fp.mtime_ns)
    if len(keys) > 5000:
        keys = set(sorted(keys)[-4000:])
    return FolderWatchState(processed_keys=keys, freshest_mtime_ns=freshest)


def _parse_first_run_date(value: Any, *, fallback: date) -> date:
    if value is None or value == "":
        return fallback
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return fallback
