from __future__ import annotations

import re

_POST_SUFFIX = r"(?:\s+and is all-in)?\s*$"
_SB_RE = re.compile(rf"^(.+?): posts small blind (\d+){_POST_SUFFIX}", re.MULTILINE)
_BB_RE = re.compile(rf"^(.+?): posts big blind (\d+){_POST_SUFFIX}", re.MULTILINE)
_ANTE_RE = re.compile(rf"^(.+?): posts (?:the )?ante (\d+){_POST_SUFFIX}", re.MULTILINE)
_LEVEL_BLINDS_RE = re.compile(r"(- Level .+? )\([^)]+\)")


def extract_blinds_from_hand(text: str) -> tuple[int, int, int | None] | None:
    """Read SB/BB/ante from posting lines; infer full level when a blind is short all-in."""
    sb_posts = [int(m.group(2)) for m in _SB_RE.finditer(text)]
    bb_posts = [int(m.group(2)) for m in _BB_RE.finditer(text)]
    if not bb_posts:
        return None

    sb = max(sb_posts) if sb_posts else 0
    bb = max(bb_posts)

    if sb == 0 and bb > 0:
        sb = bb // 2
    elif sb > 0 and bb < sb * 2:
        bb = sb * 2

    ante_posts = [int(m.group(2)) for m in _ANTE_RE.finditer(text)]
    ante = max(ante_posts) if ante_posts else None

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
