from __future__ import annotations

import re
import shutil
from collections import defaultdict
from datetime import date
from pathlib import Path

from converter.export_names import TournamentMeta
from converter.settings import Settings

_FILENAME_DATE_RE = re.compile(r"(\d{4})[_\-.](\d{1,2})[_\-.](\d{1,2})")
_COIN_DROPBOX_HEADER_RE = re.compile(
    r"(PokerStars Hand #\d+: Tournament #\d+, ).+?( - Level)"
)
_COIN_DROPBOX_TOURNAMENT_NAME = "Freeroll Hold'em No Limit"


def coin_dropbox_filename(played_on: date) -> str:
    return f"CoinPoker_{played_on.year}_{played_on.month}_{played_on.day}_0.txt"


def coin_dropbox_hand_text(hand: str) -> str:
    lines = hand.splitlines()
    if not lines:
        return hand
    lines[0] = _COIN_DROPBOX_HEADER_RE.sub(
        rf"\1{_COIN_DROPBOX_TOURNAMENT_NAME}\2",
        lines[0],
        count=1,
    )
    return "\n".join(lines)


def new_coin_dropbox_buffers() -> dict[date, list[str]]:
    return defaultdict(list)


def add_coin_dropbox_hands(
    buffers: dict[date, list[str]],
    played_on: date,
    hands: list[str],
) -> None:
    buffers[played_on].extend(coin_dropbox_hand_text(hand) for hand in hands)


def flush_coin_dropbox_copies(
    cfg: Settings,
    hands_by_date: dict[date, list[str]],
    *,
    console_print: bool,
) -> None:
    if cfg.dropbox_mode == "none" or not hands_by_date:
        return

    for played_on in sorted(hands_by_date):
        hands = hands_by_date[played_on]
        if not hands:
            continue
        dest_dir = _coin_dropbox_dest_dir(cfg, played_on)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / coin_dropbox_filename(played_on)
        payload = "\n\n".join(hands).rstrip() + "\n"
        dest_file.write_text(payload, encoding="utf-8")
        if console_print:
            print(f"[dropbox] {dest_file} ({len(hands)} hand(s))")


def mirror_chico_import(cfg: Settings, *, console_print: bool) -> None:
    if cfg.dropbox_mode == "none" or not cfg.chico_import_path:
        return

    root = cfg.chico_import_path
    if not root.exists():
        if console_print:
            print(f"[chico] Missing folder: {root}")
        return

    files = sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".txt")
    for src in files:
        dest_dir, dest_name = _chico_dest(cfg, src)
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest_dir / dest_name)
        if console_print:
            print(f"[chico] {src.name} -> {dest_dir / dest_name}")


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

    dest_dir = _room_dest_dir(cfg, room, meta)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / (dest_name or source_file.name)
    shutil.copy2(source_file, dest_file)
    if console_print:
        print(f"[dropbox] {dest_file}")


def _coin_dropbox_dest_dir(cfg: Settings, played_on: date) -> Path:
    return (
        cfg.dropbox_base_path
        / "CoinPoker"
        / str(played_on.year)
        / f"{played_on.month:02d}"
    )


def _chico_dest(cfg: Settings, src: Path) -> tuple[Path, str]:
    m = _FILENAME_DATE_RE.search(src.name)
    if not m:
        return cfg.dropbox_base_path / "Chico" / "Misc", src.name

    year = m.group(1)
    month = m.group(2).zfill(2)
    return cfg.dropbox_base_path / "Chico" / year / month, src.name


def _room_dest_dir(cfg: Settings, room: str, meta: TournamentMeta) -> Path:
    year = str(meta.played_on.year)
    base = cfg.dropbox_base_path

    if room == "ggpoker_ok":
        return base / "GG" / "hands" / year

    if room == "uppoker":
        return base / "UPpoker" / "hands" / year

    if room == "poker_planets":
        return base / "PokerPlanets" / year

    if room == "coinpoker":
        return _coin_dropbox_dest_dir(cfg, meta.played_on)

    return base / "Misc"
