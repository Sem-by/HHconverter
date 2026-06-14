from __future__ import annotations

import re

from converter.player_names import PP_PLAYER_TOKEN, parse_seat_stacks

_DEALT_TO_RE = re.compile(r"^Dealt to (\S+)", re.MULTILINE)


def detect_pp_hero_token(blocks: list[str]) -> str:
    """Return the real hero screen name from PokerPlanets import hands."""

    for block in blocks:
        for match in _DEALT_TO_RE.finditer(block):
            name = match.group(1)
            if not PP_PLAYER_TOKEN(name):
                return name

        for token, _ in parse_seat_stacks(block):
            if not PP_PLAYER_TOKEN(token):
                return token

    raise ValueError("Could not detect PokerPlanets hero in hand history")
