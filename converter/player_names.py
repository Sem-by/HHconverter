from __future__ import annotations

import random
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

_SEAT_LINE_RE = re.compile(
    r"^Seat \d+:\s+(\S+)\s+\([₮$€]?([\d,]+(?:\.\d+)?)\s+in chips\)",
    re.MULTILINE,
)
_TABLE_ID_RE = re.compile(
    r"^Table\s+'(.+?)'\s+\d+-max\s+Seat\s+#\d+\s+is\s+the\s+button\s*$",
    re.I | re.M,
)
_MONEY_AMT = r"[₮$€]?([\d,]+(?:\.\d+)?)"
_POST_RE = re.compile(
    rf"^(\S+):\s+posts(?:\s+(?:the\s+)?(?:small\s+blind|big\s+blind|ante))?\s+{_MONEY_AMT}",
    re.I,
)
_BET_RE = re.compile(rf"^(\S+):\s+bets\s+{_MONEY_AMT}", re.I)
_CALL_RE = re.compile(rf"^(\S+):\s+calls\s+{_MONEY_AMT}", re.I)
_RAISE_RE = re.compile(
    rf"^(\S+):\s+raises\s+{_MONEY_AMT}\s+to\s+{_MONEY_AMT}",
    re.I,
)
_RETURN_RE = re.compile(rf"^(\S+):\s+RETURN\s+{_MONEY_AMT}", re.I)
_UNCALLED_RE = re.compile(
    rf"^Uncalled bet\s+\({_MONEY_AMT}\)\s+returned to\s+(\S+)",
    re.I,
)
_COLLECTED_RE = re.compile(rf"^(\S+)\s+collected\s+{_MONEY_AMT}\s+from\s+pot", re.I)
_STREET_RE = re.compile(
    r"^\*\*\*\s+(HOLE CARDS|FLOP|TURN|RIVER|SHOW\s*DOWN|SHOWDOWN|SUMMARY)\s*\*\*\*",
    re.I,
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


def _to_chip_units(raw: str) -> int:
    """Integer chip units for matching (cents for cash decimals)."""
    return int(round(float(raw.replace(",", "")) * 100))


def _to_tourney_chips(raw: str) -> int:
    return int(round(float(raw.replace(",", ""))))


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
    """Assign random screen names; reuse when stack matches the prior hand.

    Used for tournament / single-table flows (PokerPlanets, Coin tournaments).
    """

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


@dataclass
class _TableEndState:
    """End-of-hand stacks for one cash table session (screen name -> cents)."""

    name_stacks: dict[str, int]
    all_stacks: list[int]


class CashMultiTableNameSession:
    """Rename cash opponents with continuity across interleaved tables.

    Coin cash files mix tables, re-anonymize hex tokens every hand, and often
    interleave several concurrent sessions that share the same table number.
    Continuity is keyed by (table id, hand-id session prefix) and matched via
    end-of-hand stacks. Companion stacks break ties when sizes collide.
    """

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
        # (table_id, hand_id_prefix) -> last end-of-hand state for that session
        self._by_session: dict[tuple[str, int], _TableEndState] = {}

    def reset(self) -> None:
        self._used_names.clear()
        self._by_session.clear()

    def map_players(self, text: str) -> str:
        table_id = cash_table_id(text) or ""
        prefix = cash_hand_session_prefix(text)
        seats = parse_seat_stacks_cents(text)
        targets = [(token, stack) for token, stack in seats if self._should_rename(token)]
        all_stacks = [stack for _, stack in seats]

        hand_map: dict[str, str] = {}
        taken: set[str] = set()
        session_key = (table_id, prefix if prefix is not None else -1)
        prev = self._by_session.get(session_key)
        if prev is None:
            prev = self._best_stack_lineage(table_id, all_stacks)
        unmatched = list(targets)

        if prev and unmatched:
            self._match_by_stacks(unmatched, all_stacks, prev, hand_map, taken)

        for token, _stack in unmatched:
            if token in hand_map:
                continue
            name = self._new_name()
            hand_map[token] = name
            taken.add(name)

        end_by_token = compute_end_stacks_cents(text)
        name_stacks: dict[str, int] = {}
        for token, start_stack in targets:
            name = hand_map.get(token)
            if not name:
                continue
            name_stacks[name] = end_by_token.get(token, start_stack)

        all_end = [
            end_by_token.get(token, start)
            for token, start in seats
        ]
        self._by_session[session_key] = _TableEndState(
            name_stacks=name_stacks,
            all_stacks=all_end,
        )
        return apply_name_map(text, hand_map)

    def _best_stack_lineage(
        self,
        table_id: str,
        all_stacks: list[int],
    ) -> _TableEndState | None:
        """Fallback when session prefix is new: resume lineage by stack fingerprint."""
        if not all_stacks or not self._by_session:
            return None
        start_c = Counter(all_stacks)
        best: _TableEndState | None = None
        best_score = 0
        for (tid, _prefix), state in self._by_session.items():
            if tid != table_id or not state.all_stacks:
                continue
            score = _multiset_overlap(start_c, Counter(state.all_stacks))
            if score > best_score:
                best_score = score
                best = state
        # Require a strong fingerprint so unrelated sessions do not merge.
        min_need = max(2, (len(all_stacks) + 1) // 2)
        if best is None or best_score < min_need:
            return None
        return best

    def _match_by_stacks(
        self,
        unmatched: list[tuple[str, int]],
        all_stacks: list[int],
        prev: _TableEndState,
        hand_map: dict[str, str],
        taken: set[str],
    ) -> None:
        prev_by_stack: dict[int, list[str]] = defaultdict(list)
        for name, stack in prev.name_stacks.items():
            if name not in taken:
                prev_by_stack[stack].append(name)

        curr_by_stack: dict[int, list[str]] = defaultdict(list)
        for token, stack in unmatched:
            if token not in hand_map:
                curr_by_stack[stack].append(token)

        # Pass 1: unique stack on both sides.
        for stack, tokens in list(curr_by_stack.items()):
            names = [n for n in prev_by_stack.get(stack, []) if n not in taken]
            if len(tokens) == 1 and len(names) == 1:
                token = tokens[0]
                name = names[0]
                hand_map[token] = name
                taken.add(name)
                curr_by_stack[stack] = []
                prev_by_stack[stack] = [n for n in prev_by_stack[stack] if n != name]

        # Pass 2: ambiguous stacks — score by companion-stack multiset overlap.
        for stack, tokens in curr_by_stack.items():
            names = [n for n in prev_by_stack.get(stack, []) if n not in taken]
            if not tokens or not names:
                continue
            for token in list(tokens):
                if token in hand_map:
                    continue
                companions = _companions(all_stacks, stack)
                best_name: str | None = None
                best_score = -1
                tied = False
                for name in names:
                    if name in taken:
                        continue
                    prev_companions = _companions(
                        prev.all_stacks,
                        prev.name_stacks[name],
                    )
                    score = _multiset_overlap(companions, prev_companions)
                    if score > best_score:
                        best_score = score
                        best_name = name
                        tied = False
                    elif score == best_score and best_name is not None:
                        tied = True
                if best_name is not None and not tied:
                    hand_map[token] = best_name
                    taken.add(best_name)

        # Pass 3: unique leftovers after companion disambiguation.
        for stack, tokens in curr_by_stack.items():
            left_tokens = [t for t in tokens if t not in hand_map]
            left_names = [n for n in prev_by_stack.get(stack, []) if n not in taken]
            if len(left_tokens) == 1 and len(left_names) == 1:
                hand_map[left_tokens[0]] = left_names[0]
                taken.add(left_names[0])

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


def cash_hand_session_prefix(text: str) -> int | None:
    """Coin hand-id high digits identify a table session (low digits = sequence)."""
    m = re.search(r"Hand\s+#(\d+)", text)
    if not m:
        return None
    return int(m.group(1)) // 100_000


def _companions(stacks: list[int], self_stack: int) -> Counter[int]:
    """Stacks of everyone else at the table (one copy of self_stack removed)."""
    counts = Counter(stacks)
    if counts[self_stack] > 0:
        counts[self_stack] -= 1
        if counts[self_stack] == 0:
            del counts[self_stack]
    return counts


def _multiset_overlap(a: Counter[int], b: Counter[int]) -> int:
    return sum(min(a[k], b[k]) for k in a.keys() | b.keys())


def cash_table_id(text: str) -> str | None:
    m = _TABLE_ID_RE.search(text)
    return m.group(1).strip() if m else None


def parse_seat_stacks(text: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for m in _SEAT_LINE_RE.finditer(text):
        token = m.group(1)
        stack = _to_tourney_chips(m.group(2))
        out.append((token, stack))
    return out


def parse_seat_stacks_cents(text: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for m in _SEAT_LINE_RE.finditer(text):
        token = m.group(1)
        stack = _to_chip_units(m.group(2))
        out.append((token, stack))
    return out


def compute_end_stacks_cents(text: str) -> dict[str, int]:
    """Approximate end-of-hand stacks (cents) from seats + action lines."""
    stacks = dict(parse_seat_stacks_cents(text))
    if not stacks:
        return stacks

    street_in: dict[str, int] = defaultdict(int)
    for line in text.splitlines():
        stripped = line.strip()
        if _STREET_RE.match(stripped):
            street_in.clear()
            continue

        m = _POST_RE.match(stripped)
        if m and m.group(1) in stacks:
            amt = _to_chip_units(m.group(2))
            stacks[m.group(1)] -= amt
            street_in[m.group(1)] += amt
            continue

        m = _RAISE_RE.match(stripped)
        if m and m.group(1) in stacks:
            to_amt = _to_chip_units(m.group(3))
            already = street_in[m.group(1)]
            add = to_amt - already
            if add > 0:
                stacks[m.group(1)] -= add
                street_in[m.group(1)] = to_amt
            continue

        m = _BET_RE.match(stripped)
        if m and m.group(1) in stacks:
            amt = _to_chip_units(m.group(2))
            stacks[m.group(1)] -= amt
            street_in[m.group(1)] += amt
            continue

        m = _CALL_RE.match(stripped)
        if m and m.group(1) in stacks:
            amt = _to_chip_units(m.group(2))
            stacks[m.group(1)] -= amt
            street_in[m.group(1)] += amt
            continue

        m = _RETURN_RE.match(stripped)
        if m and m.group(1) in stacks:
            amt = _to_chip_units(m.group(2))
            stacks[m.group(1)] += amt
            street_in[m.group(1)] = max(0, street_in[m.group(1)] - amt)
            continue

        m = _UNCALLED_RE.match(stripped)
        if m:
            amt = _to_chip_units(m.group(1))
            name = m.group(2)
            if name in stacks:
                stacks[name] += amt
                street_in[name] = max(0, street_in[name] - amt)
            continue

        m = _COLLECTED_RE.match(stripped)
        if m and m.group(1) in stacks:
            stacks[m.group(1)] += _to_chip_units(m.group(2))
            continue

    return stacks


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
