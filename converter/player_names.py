from __future__ import annotations

import random
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

_SEAT_LINE_RE = re.compile(
    r"^Seat \d+:\s+(.+?)\s+\([₮$€]?([\d,]+(?:\.\d+)?)\s+in chips\)",
    re.MULTILINE,
)
_TABLE_ID_RE = re.compile(
    r"^Table\s+'(.+?)'\s+\d+-max\s+Seat\s+#\d+\s+is\s+the\s+button\s*$",
    re.I | re.M,
)
_HAND_ID_RE = re.compile(r"Hand\s+#(\d+)")
_MONEY_AMT = r"[₮$€]?([\d,]+(?:\.\d+)?)"
_POST_BLIND_RE = re.compile(
    rf"^(.+?):\s+posts\s+(?:small|big)\s+blind\s+{_MONEY_AMT}",
    re.I,
)
_POST_ANTE_RE = re.compile(
    rf"^(.+?):\s+posts\s+(?:the\s+)?ante\s+{_MONEY_AMT}",
    re.I,
)
_POST_GENERIC_RE = re.compile(
    rf"^(.+?):\s+posts\s+{_MONEY_AMT}",
    re.I,
)
_BET_RE = re.compile(rf"^(.+?):\s+bets\s+{_MONEY_AMT}", re.I)
_ALLIN_RE = re.compile(rf"^(.+?):\s+ALLIN\s+{_MONEY_AMT}", re.I)
_CALL_RE = re.compile(rf"^(.+?):\s+calls\s+{_MONEY_AMT}", re.I)
_RAISE_RE = re.compile(
    rf"^(.+?):\s+raises\s+{_MONEY_AMT}\s+to\s+{_MONEY_AMT}",
    re.I,
)
_RETURN_RE = re.compile(rf"^(.+?):\s+RETURN\s+{_MONEY_AMT}", re.I)
_UNCALLED_RE = re.compile(
    rf"^Uncalled bet\s+\({_MONEY_AMT}\)\s+returned to\s+(.+?)\s*$",
    re.I,
)
_COLLECTED_RE = re.compile(rf"^(.+?)\s+collected\s+{_MONEY_AMT}\s+from\s+pot", re.I)
_STREET_RE = re.compile(
    r"^\*\*\*\s+(?:(?:FIRST|SECOND)\s+)?(HOLE CARDS|FLOP|TURN|RIVER|SHOW\s*DOWN|SHOWDOWN|SUMMARY)\s*\*\*\*",
    re.I,
)
_HEADER_OR_TABLE_PREFIXES = (
    "PokerStars Hand #",
    "Poker Hand #",
    "CoinPoker Hand #",
    "PokerPlanets Hand #",
    "1WinPoker Hand #",
    "Table '",
    "Tournament '",
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
_BASE_NAMES: tuple[str, ...] = tuple(f"{f}{l}" for f in _FIRST for l in _LAST)

PP_PLAYER_TOKEN = re.compile(r"^Player\d+$").match
COIN_PLAYER_TOKEN = re.compile(r"^[0-9a-f]{8}$", re.I).match


class _NamePool:
    """O(1) random unique name generator (no dead spin once base names are exhausted)."""

    def __init__(self, name_suffix: str, rng: random.Random) -> None:
        self._suffix = name_suffix
        self._rng = rng
        self._used: set[str] = set()
        self._available: list[str] = []
        self._suffix_num = 1
        self._refill()

    def _refill(self) -> None:
        pool = list(_BASE_NAMES)
        self._rng.shuffle(pool)
        self._available = pool

    def next_name(self) -> str:
        while True:
            if not self._available:
                self._suffix_num += 1
                self._refill()
            base = self._available.pop()
            if self._suffix_num == 1:
                name = f"{base}{self._suffix}"
            else:
                name = f"{base}{self._suffix_num}{self._suffix}"
            if name not in self._used:
                self._used.add(name)
                return name

    def reset(self) -> None:
        self._used.clear()
        self._suffix_num = 1
        self._refill()


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
        self._pool = _NamePool(name_suffix, self._rng)
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
        return self._pool.next_name()

    def reset(self) -> None:
        self._pool.reset()
        self._prev_end = _StackNameMap()
        self._prev_token_names = {}


@dataclass
class _TableEndState:
    """End-of-hand stacks for one cash table session (screen name -> cents)."""

    name_stacks: dict[str, int]
    all_stacks: list[int]
    all_stacks_counts: Counter[int] = field(init=False)

    def __post_init__(self) -> None:
        self.all_stacks_counts = Counter(self.all_stacks)


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
        self._pool = _NamePool(name_suffix, self._rng)
        # (table_id, hand_id_prefix) -> last end-of-hand state for that session
        self._by_session: dict[tuple[str, int], _TableEndState] = {}

    def reset(self) -> None:
        self._pool.reset()
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

        end_by_token = compute_end_stacks_cents(text, initial_seats=seats)
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
            score = _multiset_overlap(start_c, state.all_stacks_counts)
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
        curr_counts: Counter[int] | None = None
        for stack, tokens in curr_by_stack.items():
            names = [n for n in prev_by_stack.get(stack, []) if n not in taken]
            if not tokens or not names:
                continue
            if curr_counts is None:
                curr_counts = Counter(all_stacks)
            companions = _companions_from_counter(curr_counts, stack)
            for token in list(tokens):
                if token in hand_map:
                    continue
                best_name: str | None = None
                best_score = -1
                tied = False
                for name in names:
                    if name in taken:
                        continue
                    prev_companions = _companions_from_counter(
                        prev.all_stacks_counts,
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
        return self._pool.next_name()


def cash_hand_session_prefix(text: str) -> int | None:
    """Coin hand-id high digits identify a table session (low digits = sequence)."""
    first_line = text.partition("\n")[0]
    m = _HAND_ID_RE.search(first_line)
    if not m:
        return None
    return int(m.group(1)) // 100_000


def _companions_from_counter(base: Counter[int], self_stack: int) -> Counter[int]:
    """Stacks of everyone else at the table (one copy of self_stack removed)."""
    counts = base.copy()
    if counts[self_stack] > 0:
        counts[self_stack] -= 1
        if counts[self_stack] == 0:
            del counts[self_stack]
    return counts


def _companions(stacks: list[int], self_stack: int) -> Counter[int]:
    """Stacks of everyone else at the table (one copy of self_stack removed)."""
    return _companions_from_counter(Counter(stacks), self_stack)


def _multiset_overlap(a: Counter[int], b: Counter[int]) -> int:
    if len(a) > len(b):
        a, b = b, a
    total = 0
    for k, va in a.items():
        vb = b.get(k)
        if vb:
            total += va if va < vb else vb
    return total


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


def compute_end_stacks_cents(
    text: str,
    *,
    initial_seats: list[tuple[str, int]] | None = None,
) -> dict[str, int]:
    """Approximate end-of-hand stacks (cents) from seats + action lines."""
    stacks = dict(initial_seats if initial_seats is not None else parse_seat_stacks_cents(text))
    if not stacks:
        return stacks

    street_in: dict[str, int] = defaultdict(int)
    in_summary = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped[0] == "*":
            sm = _STREET_RE.match(stripped)
            if sm:
                street_name = sm.group(1).upper()
                # Blinds posted before HOLE CARDS belong to the preflop round;
                # only clear street contributions when advancing to flop/turn/river/etc.
                if street_name != "HOLE CARDS":
                    street_in.clear()
                if street_name == "SUMMARY":
                    in_summary = True
                continue
        if in_summary:
            continue

        if ": " in stripped:
            if "posts " in stripped:
                m = _POST_ANTE_RE.match(stripped)
                if m:
                    name = m.group(1)
                    if name in stacks:
                        # Antes reduce stack but do not count toward street raises.
                        stacks[name] -= _to_chip_units(m.group(2))
                    continue

                m = _POST_BLIND_RE.match(stripped)
                if m:
                    name = m.group(1)
                    if name in stacks:
                        amt = _to_chip_units(m.group(2))
                        stacks[name] -= amt
                        street_in[name] += amt
                    continue

                m = _POST_GENERIC_RE.match(stripped)
                if m:
                    name = m.group(1)
                    if name in stacks:
                        amt = _to_chip_units(m.group(2))
                        stacks[name] -= amt
                        street_in[name] += amt
                    continue

            m = _RAISE_RE.match(stripped)
            if m:
                name = m.group(1)
                if name in stacks:
                    to_amt = _to_chip_units(m.group(3))
                    already = street_in[name]
                    add = to_amt - already
                    if add > 0:
                        stacks[name] -= add
                        street_in[name] = to_amt
                continue

            m = _BET_RE.match(stripped)
            if m:
                name = m.group(1)
                if name in stacks:
                    amt = _to_chip_units(m.group(2))
                    stacks[name] -= amt
                    street_in[name] += amt
                continue

            m = _ALLIN_RE.match(stripped)
            if m:
                name = m.group(1)
                if name in stacks:
                    amt = _to_chip_units(m.group(2))
                    stacks[name] -= amt
                    street_in[name] += amt
                continue

            m = _CALL_RE.match(stripped)
            if m:
                name = m.group(1)
                if name in stacks:
                    amt = _to_chip_units(m.group(2))
                    stacks[name] -= amt
                    street_in[name] += amt
                continue

            m = _RETURN_RE.match(stripped)
            if m:
                name = m.group(1)
                if name in stacks:
                    amt = _to_chip_units(m.group(2))
                    stacks[name] += amt
                    street_in[name] = max(0, street_in[name] - amt)
                continue
            continue

        if stripped.startswith("Uncalled bet") or stripped.startswith("uncalled bet"):
            m = _UNCALLED_RE.match(stripped)
            if m:
                amt = _to_chip_units(m.group(1))
                name = m.group(2)
                if name in stacks:
                    stacks[name] += amt
                    street_in[name] = max(0, street_in[name] - amt)
            continue

        if " collected " in stripped:
            m = _COLLECTED_RE.match(stripped)
            if m:
                name = m.group(1)
                if name in stacks:
                    stacks[name] += _to_chip_units(m.group(2))
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

    tokens = sorted(hand_map, key=len, reverse=True)
    pattern = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(t) for t in tokens) + r")(?!\w)")
    repl = lambda m: hand_map[m.group(0)]

    # Skip hand header / Table / Tournament lines so all-digit tokens (e.g. 12345678)
    # cannot corrupt Hand #, Tournament #, or table/title text.
    lines = text.splitlines(keepends=True)
    if len(lines) >= 2 and lines[0].lstrip().startswith(_HEADER_OR_TABLE_PREFIXES):
        skip = 1
        if lines[1].lstrip().startswith(_HEADER_OR_TABLE_PREFIXES):
            skip = 2
        return "".join(lines[:skip]) + pattern.sub(repl, "".join(lines[skip:]))
    return pattern.sub(repl, text)
