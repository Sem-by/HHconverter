from __future__ import annotations

import re

_SB_RE = re.compile(r"^(.+?): posts small blind (\d+)\s*$", re.MULTILINE)
_BB_RE = re.compile(r"^(.+?): posts big blind (\d+)\s*$", re.MULTILINE)
_ANTE_RE = re.compile(r"^(.+?): posts (?:the )?ante (\d+)\s*$", re.MULTILINE)
_LEVEL_BLINDS_RE = re.compile(r"(- Level .+? )\([^)]+\)")


def extract_blinds_from_hand(text: str) -> tuple[int, int, int | None] | None:
    """Read SB/BB/ante from posting lines in the hand body."""
    sb_m = _SB_RE.search(text)
    bb_m = _BB_RE.search(text)
    if not sb_m or not bb_m:
        return None

    sb = int(sb_m.group(2))
    bb = int(bb_m.group(2))

    ante: int | None = None
    ante_m = _ANTE_RE.search(text)
    if ante_m:
        ante = int(ante_m.group(2))

    return sb, bb, ante


def format_blinds_piece(sb: int, bb: int, ante: int | None) -> str:
    if ante is not None:
        return f"({sb}/{bb}({ante}))"
    return f"({sb}/{bb})"


def patch_header_blinds(header_tail: str, sb: int, bb: int, ante: int | None) -> str:
    piece = format_blinds_piece(sb, bb, ante)
    if _LEVEL_BLINDS_RE.search(header_tail):
        return _LEVEL_BLINDS_RE.sub(rf"\1{piece}", header_tail, count=1)
    return header_tail
