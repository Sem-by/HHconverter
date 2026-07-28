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
)
_SUMMARY_START = re.compile(r"^Tournament\s+#", re.I)
_GG_NAME_RE = re.compile(r"^GG\d{8}", re.I)
_UP_NAME_RE = re.compile(r"^UP\d{8}", re.I)
_YEAR_IN_NAME_RE = re.compile(r"^(?:GG|UP)(\d{4})", re.I)
_POKER_HAND_ID_RE = re.compile(r"^Poker Hand #([^\s:]+)")
_HH_FIRST_LINE_PREFIXES = (
    "Poker Hand #",
    "PokerPlanets Hand #",
    "CoinPoker Hand #",
)


@dataclass(frozen=True, slots=True)
class ZipMember:
    zip_path: Path
    member_name: str
    kind: str  # "hands" | "summaries" | "converted" | "unknown"
    room: str  # "ggpoker_ok" | "uppoker" | "coinpoker" | "unknown"
    year: int | None


def list_import_zips(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".zip")


def zip_looks_like_hand_history(path: Path) -> bool:
    """Quick probe: zip contains raw HH/summary .txt (not already-converted PokerStars)."""
    try:
        with zipfile.ZipFile(path) as zf:
            checked = 0
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = Path(info.filename).name
                if not name.lower().endswith(".txt"):
                    continue
                try:
                    raw = zf.read(info.filename)[:800]
                except KeyError:
                    continue
                text = raw.decode("utf-8-sig", errors="replace")
                first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
                if first.startswith(_HH_FIRST_LINE_PREFIXES) or _SUMMARY_START.match(first):
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
                if info.is_dir():
                    continue
                name = Path(info.filename).name
                if not name.lower().endswith(".txt"):
                    continue
                try:
                    raw = zf.read(info.filename)
                except KeyError:
                    continue
                text = raw.decode("utf-8-sig", errors="replace")
                first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
                kind = _member_kind(first)
                room = _member_room(name, first)
                year = _year_from_name(name)
                if kind in {"converted", "unknown"}:
                    continue
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


def extract_zip_member(path: Path, member_name: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as zf:
        data = zf.read(member_name)
    # Flatten archive paths but keep folder segments so same basenames do not collide.
    flat = member_name.replace("\\", "/").lstrip("/")
    safe_name = flat.replace("/", "__")
    if not safe_name.lower().endswith(".txt"):
        safe_name = f"{safe_name}.txt"
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


def extract_hand_zips_to_temp(zips: list[Path]) -> tuple[Path, list[Path]]:
    """Extract hand-history members from zips into a temp folder. Returns (tmpdir, files)."""
    tmp = Path(tempfile.mkdtemp(prefix="hhconv_zip_"))
    files: list[Path] = []
    for zpath in zips:
        for member in classify_zip(zpath):
            if member.kind != "hands":
                continue
            dest = extract_zip_member(zpath, member.member_name, tmp)
            files.append(dest)
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
    if any(first_line.startswith(p) for p in _HAND_START):
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
