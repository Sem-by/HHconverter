from __future__ import annotations

import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from converter.hand_ids import detect_poker_hand_room

_HAND_START = (
    "Poker Hand #",
    "PokerPlanets Hand #",
    "CoinPoker Hand #",
    "1WinPoker Hand #",
    "***** 888poker Hand History",
)
_GAME_NO_START = re.compile(r"^#Game No\s*:", re.I)
_SUMMARY_START = re.compile(r"^Tournament\s+#", re.I)
_GG_NAME_RE = re.compile(r"^GG\d{8}", re.I)
_UP_NAME_RE = re.compile(r"^UP\d{8}", re.I)
_YEAR_IN_NAME_RE = re.compile(r"^(?:GG|UP)(\d{4})", re.I)
_POKER_HAND_ID_RE = re.compile(r"^Poker Hand #([^\s:]+)")
_HH_FIRST_LINE_PREFIXES = (
    "Poker Hand #",
    "PokerPlanets Hand #",
    "CoinPoker Hand #",
    "1WinPoker Hand #",
    "***** 888poker Hand History",
)
_INVALID_MEMBER_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_HEADER_PROBE_BYTES = 2048


@dataclass(frozen=True, slots=True)
class ZipMember:
    zip_path: Path
    member_name: str
    kind: str  # "hands" | "summaries" | "converted" | "unknown"
    room: str  # "ggpoker_ok" | "uppoker" | "coinpoker" | "888poker" | "unknown"
    year: int | None


def list_import_zips(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".zip")


def _read_first_nonempty_line(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    """Read only the leading bytes of a zip member to inspect its first non-empty line."""
    try:
        with zf.open(info) as fh:
            raw = fh.read(_HEADER_PROBE_BYTES)
    except (KeyError, zipfile.BadZipFile, OSError):
        return ""
    text = raw.decode("utf-8-sig", errors="replace")
    for line in text.splitlines():
        stripped = line.lstrip("\ufeff").strip()
        if stripped:
            return stripped
    return ""


def _is_macos_metadata_member(filename: str) -> bool:
    parts = filename.replace("\\", "/").split("/")
    if "__MACOSX" in parts:
        return True
    name = parts[-1]
    return name.startswith("._")


def zip_looks_like_hand_history(path: Path) -> bool:
    """Quick probe: zip contains raw HH/summary .txt (not already-converted PokerStars)."""
    try:
        with zipfile.ZipFile(path) as zf:
            checked = 0
            for info in zf.infolist():
                if info.is_dir() or _is_macos_metadata_member(info.filename):
                    continue
                name = Path(info.filename).name
                if not name.lower().endswith(".txt"):
                    continue
                first = _read_first_nonempty_line(zf, info)
                if (
                    first.startswith(_HH_FIRST_LINE_PREFIXES)
                    or _GAME_NO_START.match(first)
                    or _SUMMARY_START.match(first)
                ):
                    return True
                checked += 1
                if checked >= 8:
                    break
    except (zipfile.BadZipFile, OSError):
        return False
    return False


def classify_zip(path: Path) -> list[ZipMember]:
    """Inspect zip members and classify each .txt as hands or summaries."""
    out: list[ZipMember] = []
    try:
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if info.is_dir() or _is_macos_metadata_member(info.filename):
                    continue
                name = Path(info.filename).name
                if not name.lower().endswith(".txt"):
                    continue
                first = _read_first_nonempty_line(zf, info)
                kind = _member_kind(first)
                if kind in {"converted", "unknown"}:
                    continue
                room = _member_room(name, first)
                year = _year_from_name(name)
                out.append(
                    ZipMember(
                        zip_path=path,
                        member_name=info.filename,
                        kind=kind,
                        room=room,
                        year=year,
                    )
                )
    except (zipfile.BadZipFile, OSError):
        return []
    return out


def _safe_flat_member_name(member_name: str) -> str:
    # Flatten archive paths, dropping traversal segments and illegal Windows filename chars.
    raw_parts = member_name.replace("\\", "/").split("/")
    safe_parts: list[str] = []
    for part in raw_parts:
        if not part or part in {".", ".."}:
            continue
        cleaned = _INVALID_MEMBER_CHARS_RE.sub("_", part).strip(" .")
        if cleaned:
            safe_parts.append(cleaned)
    safe_name = "__".join(safe_parts) or "member"
    if not safe_name.lower().endswith(".txt"):
        safe_name = f"{safe_name}.txt"
    return safe_name


def _write_unique_member(dest_dir: Path, member_name: str, data: bytes) -> Path:
    safe_name = _safe_flat_member_name(member_name)
    dest = dest_dir / safe_name
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        n = 2
        while True:
            candidate = dest_dir / f"{stem}__{n}{suffix}"
            if not candidate.exists():
                dest = candidate
                break
            n += 1
    dest.write_bytes(data)
    return dest


def extract_zip_member(path: Path, member_name: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as zf:
        data = zf.read(member_name)
    return _write_unique_member(dest_dir, member_name, data)


def extract_zip_members(
    path: Path,
    member_names: list[str],
    dest_dir: Path,
) -> list[Path]:
    """Extract multiple members in a single ZipFile open."""
    if not member_names:
        return []
    dest_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    with zipfile.ZipFile(path) as zf:
        for member_name in member_names:
            data = zf.read(member_name)
            out.append(_write_unique_member(dest_dir, member_name, data))
    return out


def extract_hand_zips_to_temp(zips: list[Path]) -> tuple[Path, list[Path]]:
    """Extract hand-history members from zips into a temp folder. Returns (tmpdir, files)."""
    tmp = Path(tempfile.mkdtemp(prefix="hhconv_zip_"))
    files: list[Path] = []
    for zpath in zips:
        names = [m.member_name for m in classify_zip(zpath) if m.kind == "hands"]
        files.extend(extract_zip_members(zpath, names, tmp))
    return tmp, files


def iter_summary_members(zips: list[Path]) -> list[ZipMember]:
    out: list[ZipMember] = []
    for zpath in zips:
        for member in classify_zip(zpath):
            if member.kind == "summaries" and member.room in {"ggpoker_ok", "uppoker"}:
                out.append(member)
    return out


def _member_kind(first_line: str) -> str:
    if first_line.startswith("PokerStars Hand #"):
        return "converted"
    if first_line.startswith(_HAND_START) or _GAME_NO_START.match(first_line):
        return "hands"
    if _SUMMARY_START.match(first_line):
        return "summaries"
    return "unknown"


def _member_room(filename: str, first_line: str) -> str:
    name = Path(filename).name
    if first_line.startswith("CoinPoker Hand #"):
        return "coinpoker"
    if first_line.startswith("PokerPlanets Hand #"):
        return "poker_planets"
    if first_line.startswith("1WinPoker Hand #"):
        return "onewin"
    if first_line.startswith("***** 888poker Hand History") or _GAME_NO_START.match(first_line):
        return "888poker"
    if _UP_NAME_RE.match(name):
        return "uppoker"
    if _GG_NAME_RE.match(name):
        return "ggpoker_ok"
    m = _POKER_HAND_ID_RE.match(first_line)
    if m:
        return detect_poker_hand_room(m.group(1))
    if name.upper().startswith("UP"):
        return "uppoker"
    if name.upper().startswith("GG"):
        return "ggpoker_ok"
    return "unknown"


def _year_from_name(name: str) -> int | None:
    m = _YEAR_IN_NAME_RE.match(Path(name).name)
    if m:
        return int(m.group(1))
    return None
