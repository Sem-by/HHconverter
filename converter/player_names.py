from __future__ import annotations

import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field

_SEAT_LINE_RE = re.compile(
    r"^Seat \d+:\s+(\S+)\s+\(([\d,]+(?:\.\d+)?)\s+in chips\)",
    re.MULTILINE,
)

_FIRST = (
    "Ace", "Blaze", "Cedar", "Duke", "Echo", "Finn", "Gale", "Hawk",
    "Ivan", "Jade", "Kite", "Luna", "Mako", "Nova", "Orin", "Pike",
    "Quinn", "Rex", "Sage", "Troy", "Uma", "Vex", "Wolf", "Xen",
    "York", "Zed", "Arlo", "Bryn", "Cole", "Dax", "Evan", "Fox",
)
_LAST = (
    "River", "Stone", "Marsh", "Cliff", "Brook", "Ridge", "Lake", "Peak",
    "Dune", "Grove", "Haven", "Mist", "Reed", "Sand", "Vale", "Wood",
    "Creek", "Field", "Harbor", "Knoll", "Meadow", "Pine", "Shore", "Trail",
)

PP_PLAYER_TOKEN = re.compile(r"^Player\d+$").match
COIN_PLAYER_TOKEN = re.compile(r"^[0-9a-f]{8}$", re.I).match


@dataclass
class _StackNameMap:
    by_stack: dict[int, list[str]] = field(default_factory=dict)

    def name_for_stack(self, stack: int) -> str | None:
        names = self.by_stack.get(stack, [])
        if len(names) == 1:
            return names[0]
        return None

    def record(self, stack: int, name: str) -> None:
        bucket = self.by_stack.setdefault(stack, [])
        if name not in bucket:
            bucket.append(name)


class PlayerNameSession:
    """Assign random screen names; reuse when stack matches the prior hand."""

    def __init__(
        self,
        name_suffix: str,
        should_rename: Callable[[str], bool],
        rng: random.Random | None = None,
    ) -> None:
        self._name_suffix = name_suffix
        self._should_rename = should_rename
        self._rng = rng or random.Random()
        self._used_names: set[str] = set()
        self._prev_end = _StackNameMap()
        self._prev_token_names: dict[str, str] = {}

    def map_players(self, text: str, next_hand_text: str | None = None) -> str:
        seats = parse_seat_stacks(text)
        targets = [(token, stack) for token, stack in seats if self._should_rename(token)]

        hand_map: dict[str, str] = {}
        taken_names: set[str] = set()

        for token, stack in targets:
            name = self._prev_end.name_for_stack(stack)

            if not name and token in self._prev_token_names:
                candidate = self._prev_token_names[token]
                if candidate not in taken_names:
                    name = candidate

            if not name or name in taken_names:
                name = self._new_name()

            hand_map[token] = name
            taken_names.add(name)

        text = apply_name_map(text, hand_map)

        self._prev_token_names = dict(hand_map)
        self._prev_end = build_end_stacks(hand_map, next_hand_text, self._should_rename)

        return text

    def _new_name(self) -> str:
        for _ in range(2000):
            name = f"{self._rng.choice(_FIRST)}{self._rng.choice(_LAST)}{self._name_suffix}"
            if name not in self._used_names:
                self._used_names.add(name)
                return name

        base = f"{self._rng.choice(_FIRST)}{self._rng.choice(_LAST)}"
        suffix_num = 2
        while True:
            name = f"{base}{suffix_num}{self._name_suffix}"
            if name not in self._used_names:
                self._used_names.add(name)
                return name
            suffix_num += 1

    def reset(self) -> None:
        self._used_names.clear()
        self._prev_end = _StackNameMap()
        self._prev_token_names = {}


def parse_seat_stacks(text: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for m in _SEAT_LINE_RE.finditer(text):
        token = m.group(1)
        raw = m.group(2).replace(",", "")
        stack = int(round(float(raw)))
        out.append((token, stack))
    return out


def build_end_stacks(
    hand_map: dict[str, str],
    next_hand_text: str | None,
    should_rename: Callable[[str], bool],
) -> _StackNameMap:
    end_map = _StackNameMap()
    if not next_hand_text:
        return end_map

    for token, stack in parse_seat_stacks(next_hand_text):
        if not should_rename(token):
            continue
        if token in hand_map:
            end_map.record(stack, hand_map[token])

    return end_map


def apply_name_map(text: str, hand_map: dict[str, str]) -> str:
    if not hand_map:
        return text

    for token in sorted(hand_map, key=len, reverse=True):
        name = hand_map[token]
        text = re.sub(rf"(?<!\w){re.escape(token)}(?!\w)", name, text)

    return text
