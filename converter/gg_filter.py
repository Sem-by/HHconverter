from __future__ import annotations

import re

_GG_PROMO_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(?:AoF|All[- ]In\s+(?:or\s+)?Fold)\b"),
    re.compile(r"(?i)\bAvatar Race\b"),
    re.compile(r"(?i)\bFlip & Go\b"),
    re.compile(r"(?i)\bRoshambo\b"),
)


def is_gg_promotional_hand(block: str) -> bool:
    """True for GG promotional auto-tourneys that should not be converted."""
    header = block.splitlines()[0].strip() if block.splitlines() else block.strip()
    return any(pattern.search(header) for pattern in _GG_PROMO_PATTERNS)
