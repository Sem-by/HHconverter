from __future__ import annotations

import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path

from converter.coin_convert import CoinPokerConverter, coin_tournament_id
from converter.dropbox_mirror import (
    add_coin_dropbox_hands,
    copy_room_export,
    flush_coin_dropbox_copies,
    mirror_chico_import,
    new_coin_dropbox_buffers,
)
from converter.export_names import export_filename, tournament_meta_from_blocks
from converter.gg_convert import GGPokerConverter
from converter.normalize import global_postprocess, gg_postprocess, replace_seat_token, up_postprocess
from converter.pp_convert import PokerPlanetsConverter
from converter.pp_hero import detect_pp_hero_token
from converter.settings import SOURCE_HERO_TOKEN, Settings
from converter.split_hands import detect_room_from_first_line, iter_hand_blocks
from converter.up_convert import UPokerConverter


def process_all(cfg: Settings, console_print: bool = True) -> None:
    cfg.export_path.mkdir(parents=True, exist_ok=True)

    import_files = sorted(
        p for p in cfg.import_path.rglob("*.txt") if p.is_file()
    )

    if not import_files:
        if console_print:
            print(f"[warn] No .txt files under import path: {cfg.import_path}")
        return

    total_writes = 0
    coin_dropbox_buffers = new_coin_dropbox_buffers()
    for path in import_files:
        written = _convert_import_file(
            path,
            cfg,
            console_print,
            coin_dropbox_buffers=coin_dropbox_buffers,
        )
        total_writes += written

    flush_coin_dropbox_copies(cfg, coin_dropbox_buffers, console_print=console_print)

    if console_print:
        print(
            f"[done] {len(import_files)} import file(s) -> {total_writes} export file(s) "
            f"in {cfg.export_path}"
        )

    mirror_chico_import(cfg, console_print=console_print)

    if cfg.clear_import_after_convert:
        _clear_import_folder(cfg.import_path, console_print=console_print)


def _clear_import_folder(import_path: Path, *, console_print: bool) -> None:
    removed = 0
    for path in sorted(import_path.rglob("*.txt")):
        if path.is_file():
            path.unlink()
            removed += 1
    if console_print and removed:
        print(f"[clear] Removed {removed} file(s) from {import_path}")


def _convert_import_file(
    path: Path,
    cfg: Settings,
    console_print: bool,
    *,
    coin_dropbox_buffers: dict[date, list[str]],
) -> int:
    pairs: list[tuple[str, str]] = []

    for block in iter_hand_blocks(path):
        if not block:
            continue
        first = block.splitlines()[0].lstrip()
        room = detect_room_from_first_line(first)
        if room is None:
            if console_print:
                print(f"[skip-block] Unknown room in {path.name}:\n{first!r}")
            continue
        pairs.append((room, block))

    if not pairs:
        if console_print:
            print(f"[skip] No hands parsed from {path.name}")
        return 0

    grouped_converted: dict[tuple[str, str], list[str]] = defaultdict(list)
    grouped_raw: dict[tuple[str, str], list[str]] = defaultdict(list)

    pp_blocks = [block for room, block in pairs if room == "poker_planets"]
    gg_blocks = [block for room, block in pairs if room == "ggpoker_ok"]
    up_blocks = [block for room, block in pairs if room == "uppoker"]
    coin_by_tid: dict[str, list[str]] = defaultdict(list)

    for room, block in pairs:
        if room == "coinpoker":
            coin_by_tid[coin_tournament_id(block)].append(block)

    if pp_blocks:
        pp_converter = PokerPlanetsConverter()
        converted_pp = pp_converter.convert_file_blocks(pp_blocks)
        hero_token = detect_pp_hero_token(pp_blocks)
        hero_alias = f"{hero_token}_PP"
        for converted in converted_pp:
            converted = replace_seat_token(converted, hero_token, hero_alias)
            converted = global_postprocess(converted)
            grouped_converted[("poker_planets", "")].append(converted)
        grouped_raw[("poker_planets", "")].extend(pp_blocks)

    if gg_blocks:
        gg_converter = GGPokerConverter()
        for converted in gg_converter.convert_file_blocks(gg_blocks):
            converted = replace_seat_token(
                converted,
                SOURCE_HERO_TOKEN,
                cfg.player_alias,
            )
            grouped_converted[("ggpoker_ok", "")].append(gg_postprocess(converted))
        grouped_raw[("ggpoker_ok", "")].extend(gg_blocks)

    if up_blocks:
        up_converter = UPokerConverter()
        hero_alias = f"{cfg.player_alias}_UP"
        for converted in up_converter.convert_file_blocks(up_blocks):
            converted = replace_seat_token(
                converted,
                SOURCE_HERO_TOKEN,
                hero_alias,
            )
            grouped_converted[("uppoker", "")].append(up_postprocess(converted))
        grouped_raw[("uppoker", "")].extend(up_blocks)

    if coin_by_tid:
        coin_converter = CoinPokerConverter(cfg.player_alias)
        for tid, blocks in coin_by_tid.items():
            grouped_converted[("coinpoker", tid)].extend(
                coin_converter.convert_file_blocks(blocks)
            )
            grouped_raw[("coinpoker", tid)].extend(blocks)

    writes = 0
    for key in grouped_converted:
        room, tid = key
        converted_bodies = grouped_converted[key]
        raw_bodies = grouped_raw[key]
        meta = tournament_meta_from_blocks(room, raw_bodies)
        out_name = export_filename(meta)

        export_file = cfg.export_path / out_name
        converted_payload = "\n\n".join(converted_bodies).rstrip() + "\n"
        export_file.write_text(converted_payload, encoding="utf-8")

        if cfg.dropbox_mode == "original":
            if room == "coinpoker":
                add_coin_dropbox_hands(
                    coin_dropbox_buffers,
                    meta.played_on,
                    converted_bodies,
                )
            else:
                original_payload = "\n\n".join(raw_bodies).rstrip() + "\n"
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    suffix=".txt",
                    delete=False,
                ) as tmp:
                    tmp.write(original_payload)
                    tmp_path = Path(tmp.name)
                try:
                    copy_room_export(
                        cfg,
                        room=room,
                        meta=meta,
                        source_file=tmp_path,
                        dest_name=path.name,
                        console_print=console_print,
                    )
                finally:
                    tmp_path.unlink(missing_ok=True)

        if console_print:
            print(f"[write] {export_file} ({len(converted_bodies)} hand(s))")
        writes += 1

    return writes
