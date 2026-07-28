from __future__ import annotations

import filecmp
import re
import shutil
from collections import defaultdict
from datetime import date
from pathlib import Path

from converter.coin_convert import is_coin_cash_hand
from converter.coin_format import apply_coin_h2n_header
from converter.export_names import TournamentMeta
from converter.settings import Settings, is_path_set

_FILENAME_DATE_RE = re.compile(r"(\d{4})[_\-.](\d{1,2})[_\-.](\d{1,2})")
_SUMMARY_YEAR_RE = re.compile(r"^(?:GG|UP)(\d{4})", re.I)


def coin_dropbox_filename(played_on: date, *, cash: bool = False) -> str:
    kind = "cash_" if cash else ""
    return f"CoinPoker_{kind}{played_on.year}_{played_on.month}_{played_on.day}_0.txt"


def coin_dropbox_hand_text(hand: str) -> str:
    lines = hand.splitlines()
    if not lines:
        return hand
    # Cash hands stay as PokerStars cash; tournament Dropbox uses H2N Freeroll title.
    if "Hold'em No Limit ($" in lines[0] or "Hold'em No Limit (€" in lines[0]:
        return hand
    if is_coin_cash_hand(hand):
        return hand
    lines[0] = apply_coin_h2n_header(lines[0])
    return "\n".join(lines)


def new_coin_dropbox_buffers() -> dict[tuple[date, bool], list[str]]:
    return defaultdict(list)


def add_coin_dropbox_hands(
    buffers: dict[tuple[date, bool], list[str]],
    played_on: date,
    hands: list[str],
    *,
    cash: bool = False,
) -> None:
    buffers[(played_on, cash)].extend(coin_dropbox_hand_text(hand) for hand in hands)


def flush_coin_dropbox_copies(
    cfg: Settings,
    hands_by_key: dict[tuple[date, bool], list[str]],
    *,
    console_print: bool,
) -> None:
    if cfg.dropbox_mode == "none" or not hands_by_key:
        return

    for played_on, cash in sorted(hands_by_key):
        hands = hands_by_key[(played_on, cash)]
        if not hands:
            continue
        dest_dir = _coin_dropbox_dest_dir(cfg, played_on)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / coin_dropbox_filename(played_on, cash=cash)
        payload = "\n\n".join(hands).rstrip() + "\n"
        dest_file.write_text(payload, encoding="utf-8")
        if console_print:
            print(f"[dropbox] {dest_file} ({len(hands)} hand(s))")


def mirror_chico_import(cfg: Settings, *, console_print: bool) -> list[Path]:
    """Copy Chico .txt files to Dropbox. Returns source files that were copied."""
    copied: list[Path] = []
    if cfg.dropbox_mode == "none" or not cfg.chico_import_path:
        return copied

    root = cfg.chico_import_path
    if not root.exists():
        if console_print:
            print(f"[chico] Missing folder: {root}")
        return copied

    files = sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".txt")
    for src in files:
        dest_dir, dest_name = _chico_dest(cfg, src)
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest_dir / dest_name)
        copied.append(src)
        if console_print:
            print(f"[chico] {src.name} -> {dest_dir / dest_name}")
    return copied


def copy_room_export(
    cfg: Settings,
    *,
    room: str,
    meta: TournamentMeta,
    source_file: Path,
    dest_name: str | None = None,
    console_print: bool,
) -> None:
    if cfg.dropbox_mode == "none":
        return

    dest_dir = room_hands_dir(cfg, room, meta.played_on.year)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / (dest_name or source_file.name)
    shutil.copy2(source_file, dest_file)
    if console_print:
        print(f"[dropbox] {dest_file}")


def copy_summary_file(
    cfg: Settings,
    *,
    room: str,
    year: int,
    source_file: Path,
    dest_name: str | None = None,
    console_print: bool,
) -> None:
    if cfg.dropbox_mode == "none":
        return
    dest_dir = room_summaries_dir(cfg, room, year)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / (dest_name or source_file.name)
    shutil.copy2(source_file, dest_file)
    if console_print:
        print(f"[dropbox-summary] {dest_file}")


def room_hands_dir(cfg: Settings, room: str, year: int) -> Path:
    base = cfg.dropbox_base_path
    year_s = str(year)
    if room == "ggpoker_ok":
        return base / "GG" / year_s / "hands"
    if room == "uppoker":
        return base / "UPPoker" / year_s / "hands"
    if room == "poker_planets":
        return base / "PokerPlanets" / year_s
    if room == "coinpoker":
        return base / "CoinPoker" / year_s
    return base / "Misc"


def room_summaries_dir(cfg: Settings, room: str, year: int) -> Path:
    base = cfg.dropbox_base_path
    year_s = str(year)
    if room == "ggpoker_ok":
        return base / "GG" / year_s / "summaries"
    if room == "uppoker":
        return base / "UPPoker" / year_s / "summaries"
    return base / "Misc" / year_s / "summaries"


def migrate_dropbox_layout(cfg: Settings, *, console_print: bool) -> None:
    """Move old Dropbox layouts (GG/UP hands+summaries order, Chico months, UPpoker name)."""
    if cfg.dropbox_mode == "none" or not is_path_set(cfg.dropbox_base_path):
        return
    base = cfg.dropbox_base_path
    if not base.is_dir():
        return

    _migrate_room_kind_year_under(base, "GG", "hands", console_print=console_print)
    _migrate_room_kind_year_under(base, "GG", "summaries", console_print=console_print)
    _migrate_up_layouts(base, console_print=console_print)
    _migrate_chico_months(base, console_print=console_print)


def year_from_summary_name(name: str) -> int | None:
    m = _SUMMARY_YEAR_RE.match(Path(name).name)
    if m:
        return int(m.group(1))
    return None


def _coin_dropbox_dest_dir(cfg: Settings, played_on: date) -> Path:
    return (
        cfg.dropbox_base_path
        / "CoinPoker"
        / str(played_on.year)
        / str(played_on.month)
    )


def _chico_dest(cfg: Settings, src: Path) -> tuple[Path, str]:
    m = _FILENAME_DATE_RE.search(src.name)
    if not m:
        return cfg.dropbox_base_path / "Chico" / "Misc", src.name

    year = m.group(1)
    month = f"{int(m.group(2)):02d}"
    return cfg.dropbox_base_path / "Chico" / year / month, src.name


def _migrate_room_kind_year_under(
    base: Path,
    room: str,
    kind: str,
    *,
    console_print: bool,
) -> None:
    """``{room}/{kind}/{year}`` → ``{room}/{year}/{kind}``."""
    old_root = base / room / kind
    if not old_root.is_dir():
        return
    for year_dir in sorted(p for p in old_root.iterdir() if p.is_dir() and p.name.isdigit()):
        new_dir = base / room / year_dir.name / kind
        if _relocate_dir(year_dir, new_dir, console_print=console_print):
            _remove_if_empty(old_root)
            _remove_if_empty(base / room / kind)


_JUNK_NAMES = frozenset(
    {
        "desktop.ini",
        "thumbs.db",
        ".ds_store",
        "icon\r",
    }
)


def _is_junk_name(name: str) -> bool:
    return name.lower() in _JUNK_NAMES or name.startswith("~$")


def _migrate_up_layouts(base: Path, *, console_print: bool) -> None:
    """Normalize UPpoker/UPPoker trees to ``UPPoker/{year}/hands|summaries``."""
    # Old order: {name}/hands|summaries/{year} → UPPoker/{year}/hands|summaries
    # Deduplicate by resolved path (Windows: UPpoker == UPPoker).
    seen_kind_roots: set[tuple[str, str]] = set()
    for old_name in ("UPpoker", "UPPoker"):
        for kind in ("hands", "summaries"):
            old_root = base / old_name / kind
            if not old_root.is_dir():
                continue
            try:
                root_key = str(old_root.resolve()).lower()
            except OSError:
                root_key = str(old_root).lower()
            if (root_key, kind) in seen_kind_roots:
                continue
            seen_kind_roots.add((root_key, kind))

            for year_dir in sorted(
                p for p in old_root.iterdir() if p.is_dir() and p.name.isdigit()
            ):
                new_dir = base / "UPPoker" / year_dir.name / kind
                _relocate_dir(year_dir, new_dir, console_print=console_print)

            _purge_empty_dir(old_root)
            _purge_empty_dir(base / old_name)

    # Year-first under legacy UPpoker name only when distinct from UPPoker.
    uppoker = base / "UPpoker"
    uppoker_target = base / "UPPoker"
    try:
        same_room = uppoker.is_dir() and uppoker_target.is_dir() and (
            uppoker.resolve() == uppoker_target.resolve()
        )
    except OSError:
        same_room = False

    if uppoker.is_dir() and not same_room:
        for year_dir in sorted(
            p for p in uppoker.iterdir() if p.is_dir() and p.name.isdigit()
        ):
            for kind in ("hands", "summaries"):
                old_dir = year_dir / kind
                if not old_dir.is_dir():
                    continue
                new_dir = base / "UPPoker" / year_dir.name / kind
                if _relocate_dir(old_dir, new_dir, console_print=console_print):
                    _purge_empty_dir(year_dir)
        for kind in ("hands", "summaries"):
            _purge_empty_dir(uppoker / kind)
        _purge_empty_dir(uppoker)

    # Strip leftover empty old-style kind folders under UPPoker.
    for kind in ("hands", "summaries"):
        _purge_empty_dir(base / "UPPoker" / kind)

    # Windows is case-insensitive: force visible folder name to UPPoker.
    _fix_dir_name_casing(base, "UPPoker", console_print=console_print)


def _fix_dir_name_casing(
    parent: Path,
    desired_name: str,
    *,
    console_print: bool,
) -> None:
    """Rename a child dir so its on-disk casing matches ``desired_name`` (Windows)."""
    if not parent.is_dir():
        return
    match = next(
        (p for p in parent.iterdir() if p.is_dir() and p.name.lower() == desired_name.lower()),
        None,
    )
    if match is None or match.name == desired_name:
        return
    tmp = match.with_name(f"{desired_name}.__hhconv_case__")
    try:
        match.rename(tmp)
        tmp.rename(match.with_name(desired_name))
    except OSError:
        if tmp.exists() and not match.exists():
            try:
                tmp.rename(match)
            except OSError:
                pass
        if console_print:
            print(f"[dropbox-migrate] CASE RENAME FAILED: {match.name} -> {desired_name}")
        return
    if console_print:
        print(f"[dropbox-migrate] renamed {match.name} -> {desired_name}")


def _migrate_chico_months(base: Path, *, console_print: bool) -> None:
    chico = base / "Chico"
    if not chico.is_dir():
        return
    for year_dir in sorted(p for p in chico.iterdir() if p.is_dir() and p.name.isdigit()):
        for month_dir in sorted(p for p in year_dir.iterdir() if p.is_dir()):
            if not month_dir.name.isdigit():
                continue
            padded = f"{int(month_dir.name):02d}"
            if month_dir.name == padded:
                continue
            new_dir = year_dir / padded
            _relocate_dir(month_dir, new_dir, console_print=console_print)


def _relocate_dir(old_dir: Path, new_dir: Path, *, console_print: bool) -> bool:
    """Copy old_dir → new_dir (overwrite), verify, then delete old_dir."""
    if not old_dir.is_dir():
        return False
    try:
        if old_dir.resolve() == new_dir.resolve():
            return False
    except OSError:
        return False

    new_dir.mkdir(parents=True, exist_ok=True)
    for src in old_dir.rglob("*"):
        if not src.is_file() or _is_junk_name(src.name):
            continue
        rel = src.relative_to(old_dir)
        dest = new_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Always overwrite so a partial prior migrate cannot fail verification.
        shutil.copy2(src, dest)

    if not _dirs_match(old_dir, new_dir):
        if console_print:
            print(f"[dropbox-migrate] VERIFY FAILED: {old_dir} -> {new_dir}")
        return False

    shutil.rmtree(old_dir, ignore_errors=True)
    if old_dir.exists():
        # Dropbox / locked junk: strip and retry once.
        _purge_empty_dir(old_dir)
        if old_dir.exists():
            if console_print:
                print(f"[dropbox-migrate] REMOVE FAILED (left in place): {old_dir}")
            return False

    if console_print:
        print(f"[dropbox-migrate] {old_dir} -> {new_dir}")
    return True


def _dirs_match(left: Path, right: Path) -> bool:
    left_files = {
        p.relative_to(left): p
        for p in left.rglob("*")
        if p.is_file() and not _is_junk_name(p.name)
    }
    right_files = {
        p.relative_to(right): p
        for p in right.rglob("*")
        if p.is_file() and not _is_junk_name(p.name)
    }
    if set(left_files) - set(right_files):
        return False
    for rel, left_path in left_files.items():
        right_path = right_files[rel]
        if left_path.stat().st_size != right_path.stat().st_size:
            return False
        if not filecmp.cmp(left_path, right_path, shallow=False):
            return False
    return True


def _purge_empty_dir(path: Path) -> None:
    """Remove directory if empty or only junk / empty children remain."""
    if not path.is_dir():
        return
    try:
        children = list(path.iterdir())
    except OSError:
        return
    for child in children:
        if child.is_dir():
            _purge_empty_dir(child)
        elif _is_junk_name(child.name):
            try:
                child.unlink(missing_ok=True)
            except OSError:
                pass
    try:
        if not any(path.iterdir()):
            path.rmdir()
    except OSError:
        pass


def _remove_if_empty(path: Path) -> None:
    _purge_empty_dir(path)
