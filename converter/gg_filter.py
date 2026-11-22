from __future__ import annotations

import re

_GG_PROMO_RE = re.compile(
    r"\b(?:AoF|All[- ]In\s+(?:or\s+)?Fold|Avatar Race|Flip & Go|Roshambo)\b",
    re.I,
)


def is_gg_promotional_hand(block: str) -> bool:
    """True for GG promotional auto-tourneys that should not be converted."""
    header = block.partition("\n")[0].strip()
    return bool(_GG_PROMO_RE.search(header))
