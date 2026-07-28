from __future__ import annotations

import re
import shutil
import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path

from converter.coin_convert import (
    CoinPokerConverter,
    coin_group_key,
    is_coin_cash_hand,
)
from converter.dropbox_mirror import (
    add_coin_dropbox_hands,
    copy_room_export,
    copy_summary_file,
    flush_coin_dropbox_copies,
    migrate_dropbox_layout,
    mirror_chico_import,
    new_coin_dropbox_buffers,
    year_from_summary_name,
)
from converter.export_names import export_filename, tournament_meta_from_blocks
from converter.gg_convert import GGPokerConverter
from converter.import_state import (
    FolderWatchState,
    ImportWatchStore,
    first_run_min_mtime_ns,
    folder_key,
    load_watch_store,
    mark_processed,
    save_watch_store,
    select_new_files,
)
from converter.normalize import global_postprocess, gg_postprocess, replace_seat_token, up_postprocess
from converter.pp_convert import PokerPlanetsConverter
from converter.pp_hero import detect_pp_hero_token
from converter.settings import SOURCE_HERO_TOKEN, Settings, is_path_set
from converter.split_hands import detect_room_from_first_line, iter_hand_blocks
from converter.up_convert import UPpokerConverter
from converter.zip_import import (
    classify_zip,
    extract_zip_member,
    iter_summary_members,
    list_import_zips,
    zip_looks_like_hand_history,
)

# Temporary: set True to resume CoinPoker tournament Dropbox copies (cash stays off).
_COIN_DROPBOX_ENABLED = False


def process_all(cfg: Settings, console_print: bool = True) -> None:
    cfg.export_path.mkdir(parents=True, exist_ok=True)

    if cfg.dropbox_mode == "original":
        migrate_dropbox_layout(cfg, console_print=console_print)

    watch_store = load_watch_store()
    # Persist first-run date on first Convert so Downloads filtering is stable.
    save_watch_store(watch_store)
    watch_state = watch_store.folders
    downloads_min_mtime_ns = first_run_min_mtime_ns(watch_store.first_run_date)

    # Candidates are fingerprinted/cleared only after a successful convert (or intentional skip).
    watched_candidates: dict[str, list[Path]] = defaultdict(list)
    # Non-HH Downloads zips are always fingerprinted so we do not re-probe them every run.
    watched_always: dict[str, list[Path]] = defaultdict(list)
    watched_clearable: list[Path] = []

    import_files = _collect_import_txt_files(
        cfg,
        watch_state,
        watched_candidates,
        watched_clearable,
        downloads_min_mtime_ns=downloads_min_mtime_ns,
    )
    zip_files = _collect_zip_files(
        cfg,
        watch_state,
        watched_candidates,
        watched_always,
        watched_clearable,
        downloads_min_mtime_ns=downloads_min_mtime_ns,
    )

    tmp_dirs: list[Path] = []
    try:
        extracted_by_zip: dict[str, list[Path]] = {}
        for zpath in zip_files:
            extracted = _extract_hand_members(zpath, tmp_dirs)
            extracted_by_zip[_path_key(zpath)] = extracted
            import_files.extend(extracted)

        summary_zip_keys: set[str] = set()
        if cfg.dropbox_mode == "original":
            summary_zip_keys = {
                _path_key(p)
                for p in _copy_summaries_from_zips(
                    cfg, zip_files, console_print=console_print
                )
            }

        writes_by_path: dict[str, int] = {}
        if not import_files:
            if console_print:
                print(f"[warn] No hand history files to convert")
            # Still mirror Chico / clear if configured.
        else:
            total_writes = 0
            coin_dropbox_buffers = new_coin_dropbox_buffers()
            for path in import_files:
                written = _convert_import_file(
                    path,
                    cfg,
                    console_print,
                    coin_dropbox_buffers=coin_dropbox_buffers,
                )
                writes_by_path[_path_key(path)] = written
                total_writes += written

            flush_coin_dropbox_copies(
                cfg, coin_dropbox_buffers, console_print=console_print
            )

            if console_print:
                print(
                    f"[done] {len(import_files)} import file(s) -> {total_writes} export file(s) "
                    f"in {cfg.export_path}"
                )

        mirror_chico_import(cfg, console_print=console_print)

        success_keys = _watched_success_keys(
            watched_candidates,
            writes_by_path=writes_by_path,
            extracted_by_zip=extracted_by_zip,
            summary_zip_keys=summary_zip_keys,
        )
        watched_processed = _filter_watched_by_success(
            watched_candidates, success_keys
        )
        for key, paths in watched_always.items():
            watched_processed[key].extend(paths)

        watched_clearable = [
            path for path in watched_clearable if _path_key(path) in success_keys
        ]

        _update_watch_state(watch_store, watched_processed)

        if cfg.clear_import_after_convert:
            _clear_paths(
                [cfg.import_path],
                suffixes=(".txt", ".zip"),
                console_print=console_print,
            )

        if (
            cfg.clear_folders_after_import
            and cfg.dropbox_mode == "original"
            and cfg.import_from_folders
        ):
            # Only delete watched files that produced exports / intentional skips /
            # summary copies — never wipe empty or skipped archives.
            _clear_file_list(watched_clearable, console_print=console_print)

    finally:
        for tmp in tmp_dirs:
            shutil.rmtree(tmp, ignore_errors=True)


def _path_key(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _watched_success_keys(
    watched_candidates: dict[str, list[Path]],
    *,
    writes_by_path: dict[str, int],
    extracted_by_zip: dict[str, list[Path]],
    summary_zip_keys: set[str],
) -> set[str]:
    """Paths safe to fingerprint/clear: exports written, intentional skip, or summaries copied."""
    success: set[str] = set()
    for paths in watched_candidates.values():
        for path in paths:
            key = _path_key(path)
            if path.suffix.lower() == ".zip":
                extracted = extracted_by_zip.get(key, [])
                extracted_writes = sum(
                    writes_by_path.get(_path_key(p), 0) for p in extracted
                )
                if (
                    extracted_writes > 0
                    or key in summary_zip_keys
                    or _is_thanksholdemplayers(path.name)
                ):
                    success.add(key)
                continue
            written = writes_by_path.get(key, 0)
            if written > 0 or _is_thanksholdemplayers(path.name):
                success.add(key)
    return success


def _filter_watched_by_success(
    watched_candidates: dict[str, list[Path]],
    success_keys: set[str],
) -> dict[str, list[Path]]:
    out: dict[str, list[Path]] = defaultdict(list)
    for key, paths in watched_candidates.items():
        for path in paths:
            if _path_key(path) in success_keys:
                out[key].append(path)
    return out


def _collect_import_txt_files(
    cfg: Settings,
    watch_state: dict[str, FolderWatchState],
    watched_candidates: dict[str, list[Path]],
    watched_clearable: list[Path],
    *,
    downloads_min_mtime_ns: int,
) -> list[Path]:
    files: list[Path] = []

    if cfg.import_path.is_dir():
        files.extend(
            sorted(p for p in cfg.import_path.rglob("*.txt") if p.is_file())
        )

    if cfg.import_from_folders:
        for folder in (cfg.poker_planets_folder, cfg.downloads_folder):
            if folder is None or not is_path_set(folder) or not folder.is_dir():
                continue
            key = folder_key(folder)
            state = watch_state.get(key, FolderWatchState(set(), 0))
            # PokerPlanets client dumps HH into date/table subfolders.
            recursive = folder == cfg.poker_planets_folder
            min_mtime = (
                downloads_min_mtime_ns
                if folder == cfg.downloads_folder
                else None
            )
            new_files = select_new_files(
                folder,
                state,
                suffixes=(".txt",),
                recursive=recursive,
                min_mtime_ns=min_mtime,
            )
            files.extend(new_files)
            watched_candidates[key].extend(new_files)
            watched_clearable.extend(new_files)

    # Deduplicate by resolved path.
    seen: set[str] = set()
    unique: list[Path] = []
    for path in files:
        try:
            rk = str(path.resolve())
        except OSError:
            rk = str(path)
        if rk in seen:
            continue
        seen.add(rk)
        unique.append(path)
    return unique


def _collect_zip_files(
    cfg: Settings,
    watch_state: dict[str, FolderWatchState],
    watched_candidates: dict[str, list[Path]],
    watched_always: dict[str, list[Path]],
    watched_clearable: list[Path],
    *,
    downloads_min_mtime_ns: int,
) -> list[Path]:
    zips: list[Path] = []
    if cfg.import_path.is_dir():
        zips.extend(list_import_zips(cfg.import_path))

    if cfg.import_from_folders and cfg.downloads_folder and is_path_set(cfg.downloads_folder):
        folder = cfg.downloads_folder
        key = folder_key(folder)
        state = watch_state.get(key, FolderWatchState(set(), 0))
        new_zips = select_new_files(
            folder,
            state,
            suffixes=(".zip",),
            min_mtime_ns=downloads_min_mtime_ns,
        )
        hh_zips: list[Path] = []
        non_hh: list[Path] = []
        for zpath in new_zips:
            if zip_looks_like_hand_history(zpath):
                hh_zips.append(zpath)
            else:
                non_hh.append(zpath)
        zips.extend(hh_zips)
        # HH zips need a successful extract/convert (or summary copy) before fingerprint/clear.
        # Non-HH archives are always fingerprinted so they are not re-probed every run.
        watched_candidates[key].extend(hh_zips)
        watched_always[key].extend(non_hh)
        watched_clearable.extend(hh_zips)

    seen: set[str] = set()
    unique: list[Path] = []
    for path in zips:
        try:
            rk = str(path.resolve())
        except OSError:
            rk = str(path)
        if rk in seen:
            continue
        seen.add(rk)
        unique.append(path)
    return unique


def _is_thanksholdemplayers(name: str) -> bool:
    """Skip GG #ThanksHoldemPlayers freeroll exports (filename or title)."""
    return "thanksholdemplayers" in re.sub(r"[#\s_\-]+", "", name.casefold())


def _extract_hand_members(zpath: Path, tmp_dirs: list[Path]) -> list[Path]:
    tmp = Path(tempfile.mkdtemp(prefix="hhconv_zip_"))
    tmp_dirs.append(tmp)
    out: list[Path] = []
    for member in classify_zip(zpath):
        if member.kind != "hands":
            continue
        if _is_thanksholdemplayers(Path(member.member_name).name):
            continue
        out.append(extract_zip_member(zpath, member.member_name, tmp))
    return out


def _copy_summaries_from_zips(
    cfg: Settings,
    zips: list[Path],
    *,
    console_print: bool,
) -> set[Path]:
    """Copy GG/UP summaries from zips. Returns zip paths that contributed at least one summary."""
    copied_from: set[Path] = set()
    tmp = Path(tempfile.mkdtemp(prefix="hhconv_sum_"))
    try:
        for member in iter_summary_members(zips):
            year = member.year or year_from_summary_name(Path(member.member_name).name)
            if year is None:
                year = date.today().year
            extracted = extract_zip_member(member.zip_path, member.member_name, tmp)
            copy_summary_file(
                cfg,
                room=member.room,
                year=year,
                source_file=extracted,
                console_print=console_print,
            )
            copied_from.add(member.zip_path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return copied_from


def _update_watch_state(
    watch_store: ImportWatchStore,
    watched_processed: dict[str, list[Path]],
) -> None:
    # Always persist so first_run_date is written on the first convert.
    for key, paths in watched_processed.items():
        prev = watch_store.folders.get(key, FolderWatchState(set(), 0))
        root = Path(key)
        watch_store.folders[key] = mark_processed(
            prev,
            paths,
            root=root if root.is_dir() else None,
        )
    save_watch_store(watch_store)


def _clear_paths(
    roots: list[Path],
    *,
    suffixes: tuple[str, ...],
    console_print: bool,
) -> None:
    removed = 0
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in suffixes:
                path.unlink(missing_ok=True)
                removed += 1
    if console_print and removed:
        print(f"[clear] Removed {removed} file(s)")


def _clear_file_list(paths: list[Path], *, console_print: bool) -> None:
    removed = 0
    seen: set[str] = set()
    for path in paths:
        try:
            rk = str(path.resolve())
        except OSError:
            rk = str(path)
        if rk in seen:
            continue
        seen.add(rk)
        if path.is_file():
            path.unlink(missing_ok=True)
            removed += 1
    if console_print and removed:
        print(f"[clear] Removed {removed} watched file(s)")


def _convert_import_file(
    path: Path,
    cfg: Settings,
    console_print: bool,
    *,
    coin_dropbox_buffers: dict[tuple[date, bool], list[str]],
) -> int:
    if _is_thanksholdemplayers(path.name):
        if console_print:
            print(f"[skip] ThanksHoldemPlayers: {path.name}")
        return 0

    pairs: list[tuple[str, str]] = []

    for block in iter_hand_blocks(path):
        if not block:
            continue
        first = block.splitlines()[0].lstrip()
        if _is_thanksholdemplayers(first):
            continue
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
    coin_by_key: dict[str, list[str]] = defaultdict(list)

    for room, block in pairs:
        if room == "coinpoker":
            coin_by_key[coin_group_key(block)].append(block)

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
        up_converter = UPpokerConverter()
        hero_alias = f"{cfg.player_alias}_UP"
        for converted in up_converter.convert_file_blocks(up_blocks):
            converted = replace_seat_token(
                converted,
                SOURCE_HERO_TOKEN,
                hero_alias,
            )
            grouped_converted[("uppoker", "")].append(up_postprocess(converted))
        grouped_raw[("uppoker", "")].extend(up_blocks)

    if coin_by_key:
        coin_converter = CoinPokerConverter(
            cfg.player_alias,
            coin_as_ps=cfg.coin_as_ps,
        )
        for key, blocks in coin_by_key.items():
            grouped_converted[("coinpoker", key)].extend(
                coin_converter.convert_file_blocks(blocks)
            )
            grouped_raw[("coinpoker", key)].extend(blocks)

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
                # Temporary: disable all CoinPoker Dropbox copies.
                # When re-enabled: tournaments only — never cash.
                if _COIN_DROPBOX_ENABLED:
                    cash = bool(raw_bodies and is_coin_cash_hand(raw_bodies[0]))
                    if not cash:
                        dropbox_bodies = converted_bodies
                        if cfg.coin_as_ps:
                            dropbox_bodies = CoinPokerConverter(
                                cfg.player_alias,
                                coin_as_ps=False,
                            ).convert_file_blocks(raw_bodies)
                        add_coin_dropbox_hands(
                            coin_dropbox_buffers,
                            meta.played_on,
                            dropbox_bodies,
                            cash=False,
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
