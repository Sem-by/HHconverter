from __future__ import annotations

import argparse
import sys
from pathlib import Path

from converter.engine import process_all
from converter.settings import default_config_path, load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert multi-room tournament hand histories for Hand2Note import.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.json (default: ./config.json next to cwd)",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress prints",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    cfg_path = args.config
    if cfg_path is None:
        cfg_path = default_config_path()

    if not cfg_path.is_file():
        print(f"Missing config file: {cfg_path}", file=sys.stderr)
        return 2

    try:
        settings = load_settings(cfg_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        process_all(settings, console_print=not args.quiet)

    except OSError as exc:
        print(f"IO problem: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
