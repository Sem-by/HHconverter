from __future__ import annotations

import re


def global_postprocess(text: str, *, trim_total_pot: bool = True) -> str:
    text = re.sub(r"(?m)^Game ended:.*\n", "", text)

    def board_norm(m: re.Match[str]) -> str:
        inner = m.group(1)
        inner = inner.replace("[ ", "[").replace(" ]", "]")
        inner = re.sub(r"\s+", " ", inner.strip())
        return "Board [" + inner + "]"

    text = re.sub(r"Board \[(.*?)\]", board_norm, text, flags=re.DOTALL)

    lines_out: list[str] = []

    for line in text.splitlines():
        stripped = line.lstrip()

        if trim_total_pot and stripped.startswith("Total pot"):
            pot_only = stripped.split("|", 1)[0].rstrip()
            line = pot_only + " | Rake 0"

        lines_out.append(line.rstrip())

    text = "\n".join(lines_out)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.rstrip() + "\n"


def gg_postprocess(text: str) -> str:
    """GG export: keep Jackpot/Bingo/etc. on Total pot lines; still normalize boards."""
    return global_postprocess(text, trim_total_pot=False)


def up_postprocess(text: str) -> str:
    """UP export: keep Jackpot on Total pot; normalize boards like GG."""
    return global_postprocess(text, trim_total_pot=False)


def replace_seat_token(text: str, seat_token: str, replacement: str) -> str:
    if not seat_token:
        return text
    pattern = re.compile(r"(?<!\w)" + re.escape(seat_token) + r"(?!\w)")
    return pattern.sub(replacement, text)
