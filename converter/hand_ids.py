HAND_PREFIX_POKER_PLANETS = "111111"
HAND_PREFIX_GGPOKER = "222222"
HAND_PREFIX_COINPOKER = "333333"
HAND_PREFIX_UPPOKER = "444444"

_GG_ID_SOURCE_PREFIX = "5730"
_GG_ID_DISPLAY_PREFIX = "205730"


def poker_hand_suffix(raw_hand_id: str) -> str:
    suffix = raw_hand_id.strip()
    if suffix.upper().startswith("TM"):
        return suffix[2:]
    return suffix


def detect_poker_hand_room(raw_hand_id: str) -> str:
    """GGPoker uses numeric ``TM5730…`` ids; UPoker uses hex ``TM0ED72…`` ids."""
    suffix = poker_hand_suffix(raw_hand_id)
    if suffix.isdigit():
        return "ggpoker_ok"
    return "uppoker"


def prefixed_hand_id(prefix: str, raw_hand_id: str, *, strip_tm: bool = False) -> str:
    """Build display hand id: room prefix + suffix (optionally drop leading ``TM`` for GG)."""
    suffix = poker_hand_suffix(raw_hand_id) if strip_tm else raw_hand_id.strip()
    return f"{prefix}{suffix}"


def gg_display_hand_id(raw_hand_id: str) -> str:
    """Map GGPoker ``TM5730…`` ids to PokerStars-style ``205730…`` ids for Hand2Note."""
    suffix = poker_hand_suffix(raw_hand_id)
    if suffix.startswith(_GG_ID_SOURCE_PREFIX):
        return f"{_GG_ID_DISPLAY_PREFIX}{suffix[len(_GG_ID_SOURCE_PREFIX):]}"
    return prefixed_hand_id(HAND_PREFIX_GGPOKER, suffix)


_UP_ID_MAX_DIGITS = 12
_UP_HAND_HEX_LEN = 7
_UP_TOURNAMENT_ID_MAX_LEN = 9
_UP_TOURNAMENT_MOD = 10**9
_UP_HAND_ID_BASE = 205_872_000_000


def up_display_hand_id(raw_hand_id: str) -> str:
    """Map UPoker hex ids to 12-digit PokerStars-style ids (parallel to GG 205730…)."""
    suffix = poker_hand_suffix(raw_hand_id)
    head = suffix[:_UP_HAND_HEX_LEN]
    try:
        return str(_UP_HAND_ID_BASE + int(head, 16) % 1_000_000)
    except ValueError:
        pass
    try:
        digits = str(int(suffix, 16))
        if len(digits) > _UP_ID_MAX_DIGITS:
            digits = digits[-_UP_ID_MAX_DIGITS:]
        return digits
    except ValueError:
        return prefixed_hand_id(HAND_PREFIX_UPPOKER, suffix)


def up_display_tournament_id(raw_tid: str) -> str:
    """UP tournament ids are 19-digit snowflakes; compress to 9-digit Stars-style ids."""
    digits = raw_tid.strip()
    if not digits.isdigit():
        return digits
    if len(digits) <= _UP_TOURNAMENT_ID_MAX_LEN:
        return digits
    return str(int(digits) % _UP_TOURNAMENT_MOD)
