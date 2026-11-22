from __future__ import annotations

import re

_POST_SUFFIX = r"(?P<allin>\s+and is all-in)?\s*$"
_SB_RE = re.compile(rf"^(.+?): posts small blind ([\d,]+){_POST_SUFFIX}", re.MULTILINE)
_BB_RE = re.compile(rf"^(.+?): posts big blind ([\d,]+){_POST_SUFFIX}", re.MULTILINE)
_ANTE_RE = re.compile(rf"^(.+?): posts (?:the )?ante ([\d,]+){_POST_SUFFIX}", re.MULTILINE)
_LEVEL_BLINDS_RE = re.compile(r"(- Level .+? )\([^)]+\)")


def _chips(raw: str) -> int:
    return int(raw.replace(",", ""))


def extract_blinds_from_hand(text: str) -> tuple[int, int, int | None] | None:
    """Read SB/BB/ante from posting lines; infer full level when a blind is short all-in."""
    hole_pos = text.find("*** HOLE CARDS ***")
    posting = text[:hole_pos] if hole_pos != -1 else text

    sb_matches = list(_SB_RE.finditer(posting))
    bb_matches = list(_BB_RE.finditer(posting))
    if not bb_matches and not sb_matches:
        return None

    sb_posts = [_chips(m.group(2)) for m in sb_matches]
    bb_posts = [_chips(m.group(2)) for m in bb_matches]
    sb_all_allin = bool(sb_matches) and all(m.group("allin") for m in sb_matches)

    sb = max(sb_posts) if sb_posts else 0
    bb = max(bb_posts) if bb_posts else 0

    if bb == 0 and sb > 0:
        bb = sb * 2
    elif sb == 0 and bb > 0:
        sb = bb // 2
    elif sb_all_allin and bb > 0 and sb * 2 < bb:
        sb = bb // 2
    elif sb > 0 and bb < sb * 2:
        bb = sb * 2

    ante_posts = [_chips(m.group(2)) for m in _ANTE_RE.finditer(posting)]
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
