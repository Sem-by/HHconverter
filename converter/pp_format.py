from __future__ import annotations

import re

# Level I (75/150(20)) 2026/05/14 ...  ->  Level I (75/150(20)) - 2026/05/14 ...
_LEVEL_DATE_NO_DASH_RE = re.compile(r"\)\s+(\d{4}/)")

# Table '451075 7'(1061498) 8-max  ->  Table '451075 7' 8-max
_TABLE_INTERNAL_ID_RE = re.compile(r"^(Table\s+'[^']+')\(\d+\)(\s+)")


def normalize_pp_header_timestamp(tail: str) -> str:
    """Ensure `` - `` before the UTC timestamp (required by Hand2Note parser)."""
    if re.search(r"\)\s+-\s+\d{4}/", tail):
        return tail
    return _LEVEL_DATE_NO_DASH_RE.sub(r") - \1", tail, count=1)


def normalize_pp_table_line(line: str) -> str:
    """Remove PokerPlanets internal table id in parentheses after the table name."""
    return _TABLE_INTERNAL_ID_RE.sub(r"\1\2", line.strip())
