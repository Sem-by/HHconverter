"""Regression tests for multi-room converter bug fixes and edge cases (stdlib only)."""

from __future__ import annotations

import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest import mock

from converter.coin_convert import CoinPokerConverter
from converter.coin_format import (
    coin_postprocess,
    fix_short_blind_allin_for_h2n,
    normalize_coin_action_lines,
)
from converter.dropbox_mirror import _chico_dest, _month_from_onewin_dropbox_name
from converter.eight88_convert import convert_888_hand, eight88_tournament_meta
from converter.engine import process_all
from converter.export_names import TournamentMeta, export_filename, tournament_meta_from_blocks
from converter.gg_convert import GGPokerConverter
from converter.import_state import FolderWatchState, mark_processed, select_new_files
from converter.normalize import global_postprocess, replace_seat_token
from converter.player_names import (
    COIN_PLAYER_TOKEN,
    CashMultiTableNameSession,
    apply_name_map,
    compute_end_stacks_cents,
)
from converter.pp_blinds import extract_blinds_from_hand
from converter.pp_body import normalize_pp_body_lines
from converter.pp_hero import detect_pp_hero_token
from converter.settings import Settings, default_settings, load_settings, save_settings
from converter.split_hands import iter_hand_blocks
from converter.time_et import int_to_roman, normalize_level_piece, parse_header_timestamp
from converter.up_convert import UPpokerConverter
from converter.win1_convert import OneWinConverter
from converter.zip_import import classify_zip, extract_zip_member, zip_looks_like_hand_history


class SplitHandsTests(unittest.TestCase):
    def test_888_multihand_keeps_game_no_with_its_own_hand(self) -> None:
        raw = "\n".join(
            [
                "#Game No : 1001",
                "***** 888poker Hand History for Game 1001 ****",
                "$10/$20 Blinds No Limit Holdem - *** 15 08 2026 12:00:00",
                "Tournament #1 $5 + $0.50 Test - Table #1 6 Max (Real Money)",
                "Seat 1: A ( 1,000 )",
                "#Game No : 1002",
                "***** 888poker Hand History for Game 1002 ****",
                "$10/$20 Blinds No Limit Holdem - *** 15 08 2026 12:01:00",
                "Tournament #1 $5 + $0.50 Test - Table #1 6 Max (Real Money)",
                "Seat 1: A ( 1,200 )",
            ]
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "888.txt"
            p.write_text(raw, encoding="utf-8")
            blocks = list(iter_hand_blocks(p))

        self.assertEqual(len(blocks), 2)
        self.assertNotIn("#Game No : 1002", blocks[0])
        self.assertTrue(blocks[1].startswith("#Game No : 1002"))
        # Both hands convert cleanly (stripping #Game No).
        self.assertNotIn("#Game No", convert_888_hand(blocks[0]))
        self.assertNotIn("#Game No", convert_888_hand(blocks[1]))

    def test_concatenated_double_bom_is_stripped_from_subsequent_hands(self) -> None:
        raw = (
            "\ufeff\ufeffPoker Hand #TM5730000001: Tournament #1, $5 Hold'em No Limit - Level1(10/20) - 2026/08/17 12:00:00\n"
            "Table '1' 6-max Seat #1 is the button\n"
            "\n"
            "\ufeff\ufeffPoker Hand #TM5730000002: Tournament #1, $5 Hold'em No Limit - Level1(10/20) - 2026/08/17 12:01:00\n"
            "Table '1' 6-max Seat #2 is the button\n"
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "concat.txt"
            p.write_bytes(raw.encode("utf-8"))
            blocks = list(iter_hand_blocks(p))

        self.assertEqual(len(blocks), 2)
        self.assertTrue(blocks[0].startswith("Poker Hand #TM5730000001"))
        self.assertTrue(blocks[1].startswith("Poker Hand #TM5730000002"))

    def test_header_like_player_action_does_not_split_hand(self) -> None:
        raw = "\n".join(
            [
                "Poker Hand #TM5730000001: Tournament #1, $5 Hold'em No Limit - Level1(10/20) - 2026/08/17 12:00:00",
                "Table '1' 6-max Seat #1 is the button",
                "*** HOLE CARDS ***",
                "Poker Hand #999: folds",
                "Hero: raises 20 to 40",
            ]
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "gg.txt"
            p.write_text(raw, encoding="utf-8")
            blocks = list(iter_hand_blocks(p))

        self.assertEqual(len(blocks), 1)
        self.assertIn("Poker Hand #999: folds", blocks[0])


class TimeAndNormalizeTests(unittest.TestCase):
    def test_int_to_roman_supports_high_mtt_levels(self) -> None:
        self.assertEqual(int_to_roman(50), "L")
        self.assertEqual(int_to_roman(66), "LXVI")
        self.assertEqual(int_to_roman(100), "C")
        self.assertIsNone(int_to_roman(0))
        self.assertIsNone(int_to_roman(4000))
        self.assertIn(
            "- Level LXVI (50000/100000)",
            normalize_level_piece("Tournament #1 - Level66(50000/100000) - 2026/08/17 12:00:00"),
        )

    def test_parse_header_timestamp_handles_invalid_dates_and_offsets(self) -> None:
        self.assertIsNone(parse_header_timestamp("2026/02/30 12:00:00 UTC"))
        self.assertIsNone(parse_header_timestamp("2026/08/17 12:00:00 +99"))
        self.assertIsNone(parse_header_timestamp("2026/08/17 12:00:00 +05:99"))

    def test_replace_seat_token_handles_backslashes_and_preserves_header(self) -> None:
        hand = "\n".join(
            [
                "PokerStars Hand #1: Tournament #10, $11 Hero Bounty Hold'em No Limit - Level I (10/20) - 2026/08/17 12:00:00 UTC",
                "Table 'Hero 1' 6-max Seat #1 is the button",
                "Seat 1: Hero (1000 in chips)",
                "Dealt to Hero [Ah Kd]",
                "Hero: raises 20 to 40",
            ]
        )
        out = replace_seat_token(hand, "Hero", r"Nick\1")
        self.assertIn("$11 Hero Bounty", out)
        self.assertIn("Table 'Hero 1'", out)
        self.assertIn(r"Seat 1: Nick\1 (1000 in chips)", out)
        self.assertIn(r"Dealt to Nick\1 [Ah Kd]", out)

    def test_global_postprocess_strips_eof_game_ended_and_keeps_cash_rake_currency(self) -> None:
        text = "Total pot $3.50 | Rake $0\nGame ended: 2026/08/17 12:00:00"
        out = global_postprocess(text)
        self.assertIn("Total pot $3.50 | Rake $0", out)
        self.assertNotIn("Game ended:", out)


class PlayerNamesTests(unittest.TestCase):
    def test_compute_end_stacks_preserves_preflop_blinds_ignores_ante_and_tracks_allin(self) -> None:
        hand = "\n".join(
            [
                "CoinPoker Hand #2001000001: NLH (₮0.50/₮1.00) 2026/08/17 18:00:00 UTC",
                "Table 'T1' 6-max Seat #1 is the button",
                "Seat 1: aaaaaaaa (₮10.00 in chips)",
                "Seat 2: bbbbbbbb (₮10.00 in chips)",
                "Seat 3: Hero (₮10.00 in chips)",
                "aaaaaaaa: posts ante ₮0.10",
                "bbbbbbbb: posts ante ₮0.10",
                "Hero: posts ante ₮0.10",
                "bbbbbbbb: posts small blind ₮0.50",
                "Hero: posts big blind ₮1.00",
                "*** HOLE CARDS ***",
                "aaaaaaaa: folds",
                "bbbbbbbb: raises ₮2.00 to ₮2.50",
                "Hero: ALLIN ₮8.90",
                "bbbbbbbb: folds",
                "Hero: RETURN ₮7.40",
                "Hero collected ₮5.30 from pot",
            ]
        )
        end = compute_end_stacks_cents(hand)
        # aaaaaaaa: 1000 - 10 = 990
        self.assertEqual(end["aaaaaaaa"], 990)
        # bbbbbbbb: 1000 - 10 (ante) - 50 (SB) - 200 (raise to 250) = 740
        self.assertEqual(end["bbbbbbbb"], 740)
        # Hero: 1000 - 10 (ante) - 100 (BB) - 890 (ALLIN) + 740 (RETURN) + 530 (pot) = 1270
        self.assertEqual(end["Hero"], 1270)

    def test_apply_name_map_does_not_corrupt_numeric_header_or_tournament_id(self) -> None:
        hand = "\n".join(
            [
                "CoinPoker Hand #12345678: NLH (100/200/25) 2026/08/17 18:00:00 UTC",
                "Tournament 'Test' '12345678' 6-max Seat #1 is the button",
                "Seat 1: 12345678 (5000 in chips)",
                "12345678: folds",
            ]
        )
        out = apply_name_map(hand, {"12345678": "AceRiver"})
        self.assertIn("CoinPoker Hand #12345678:", out)
        self.assertIn("Tournament 'Test' '12345678'", out)
        self.assertIn("Seat 1: AceRiver (5000 in chips)", out)
        self.assertIn("AceRiver: folds", out)

    def test_cash_session_generates_over_1000_unique_names(self) -> None:
        session = CashMultiTableNameSession("", COIN_PLAYER_TOKEN)
        generated = {session._new_name() for _ in range(1200)}
        self.assertEqual(len(generated), 1200)


class CoinBugFixTests(unittest.TestCase):
    def test_dead_big_blind_uses_nominal_bb_for_preflop_allin_and_raises(self) -> None:
        lines = [
            "PokerStars Hand #331: Tournament #1, Test Hold'em No Limit - Level I (50/100) - 2026/08/17 18:00:00 UTC",
            "Table 'CPR_1 1' 6-max Seat #1 is the button",
            "Alice: posts small blind 50",
            "*** HOLE CARDS ***",
            "Bob: bets 80 and is all-in",
            "Cara: bets 300 and is all-in",
        ]
        out = normalize_coin_action_lines(lines)
        self.assertEqual(out[-2], "Bob: calls 80 and is all-in")
        self.assertEqual(out[-1], "Cara: raises 200 to 300 and is all-in")

    def test_preflop_non_allin_bet_computes_increment_over_bb(self) -> None:
        lines = [
            "Alice: posts small blind 50",
            "Bob: posts big blind 100",
            "*** HOLE CARDS ***",
            "Cara: bets 300",
        ]
        out = normalize_coin_action_lines(lines)
        self.assertEqual(out[-1], "Cara: raises 200 to 300")

    def test_spaced_hero_alias_normalizes_allin_and_blinds(self) -> None:
        raw = "\n".join(
            [
                "CoinPoker Hand #137369300026: NLH (50/100/10) 2026/08/17 18:03:42 UTC",
                "",
                "Tournament '$11 Test' '89453' 6-max Seat #1 is the button",
                "Seat 1: Hero (1,000 in chips)",
                "Seat 2: aaaaaaaa (2,000 in chips)",
                "Hero: posts small blind 50",
                "aaaaaaaa: posts big blind 100",
                "*** HOLE CARDS ***",
                "Dealt to aaaaaaaa [TAG]",
                "Dealt to Hero [Ah Kh]",
                "Hero: ALLIN 950",
                "aaaaaaaa: folds",
                "Hero: RETURN 850",
                "*** SHOWDOWN ***",
                "Hero collected 200 from pot",
                "*** SUMMARY ***",
                "Total pot 200",
            ]
        )
        out = CoinPokerConverter("John Doe", coin_as_ps=False).convert_hand(raw)
        self.assertIn("John Doe: raises 900 to 1000 and is all-in", out)
        self.assertNotIn("Dealt to aaaaaaaa [TAG]", out)
        self.assertIn("Dealt to John Doe [Ah Kh]", out)

    def test_dollar_in_nickname_does_not_add_currency_in_short_bb_fix(self) -> None:
        hand = "\n".join(
            [
                "PokerStars Hand #1: Tournament #1, Hold'em No Limit - Level (350/700) - 2026/01/01 0:00:00 UTC",
                "Table 'CPR_1 0' 6-max Seat #1 is the button",
                "Seat 1: SB (1000 in chips)",
                "Seat 2: Mr$Money (49 in chips)",
                "SB: posts small blind 350",
                "Mr$Money: posts big blind 49 and is all-in",
                "*** HOLE CARDS ***",
                "Uncalled bet (301) returned to SB",
                "*** FLOP *** [2c 7d Jh]",
                "*** SUMMARY ***",
                "Total pot 98 | Rake 0",
            ]
        )
        out = fix_short_blind_allin_for_h2n(hand)
        self.assertIn("SB: posts small blind 49", out)
        self.assertIn("Mr$Money: posts big blind 49 and is all-in", out)
        self.assertNotIn("posts small blind $49", out)

    def test_coin_postprocess_does_not_integerize_decimals_in_nicknames(self) -> None:
        hand = "\n".join(
            [
                "PokerStars Hand #2: Tournament #2, Hold'em No Limit - Level (200/400) - 2026/01/01 0:00:00 UTC",
                "Table 'CPR_2 0' 7-max Seat #1 is the button",
                "Seat 1: Player2.5 (1000.75 in chips)",
                "*** SUMMARY ***",
                "Total pot 400.25 | Rake 0",
            ]
        )
        out = coin_postprocess(hand)
        self.assertIn("Seat 1: Player2.5 (1001 in chips)", out)
        self.assertIn("Total pot 400 | Rake 0", out)


class PokerPlanetsBugFixTests(unittest.TestCase):
    def test_masked_cards_preserves_adjacent_visible_cards(self) -> None:
        lines = [
            "*** SHOW DOWN ***",
            "Player1: shows [## Ah]",
            "Player2: shows [Kd ##]",
            "Player3: shows [## ##]",
        ]
        out = normalize_pp_body_lines(lines)
        self.assertIn("Player1: shows [Xx Ah]", out)
        self.assertIn("Player2: shows [Kd Xx]", out)
        self.assertIn("Player3: shows [Xx Xx]", out)

    def test_allin_blind_poster_is_not_implicitly_folded(self) -> None:
        lines = [
            "Seat 1: Player1 (1000 in chips)",
            "Seat 2: Player2 (40 in chips)",
            "Seat 3: Player3 (1000 in chips)",
            "Player1: posts small blind 50",
            "Player2: posts big blind 40 and is all-in",
            "*** HOLE CARDS ***",
            "Player3: calls 50",
            "Player1: checks",
            "*** FLOP *** [Ah Kd 2c]",
        ]
        out = normalize_pp_body_lines(lines)
        self.assertNotIn("Player2: folds", out)

    def test_sits_out_before_hole_cards_is_not_converted_to_fold(self) -> None:
        lines = [
            "Seat 1: Big Boss (1000 in chips)",
            "Seat 2: Player1 (1000 in chips)",
            "Big Boss: sits out",
            "Player1: posts small blind 50",
            "Big Boss: posts big blind 100",
            "*** HOLE CARDS ***",
            "Big Boss: sits out",
            "*** SUMMARY ***",
            "Seat 1: Big Boss",
        ]
        out = normalize_pp_body_lines(lines)
        hole_idx = out.index("*** HOLE CARDS ***")
        self.assertIn("Big Boss: sits out", out[:hole_idx])
        self.assertIn("Big Boss: folds", out[hole_idx:])
        self.assertIn("Seat 1: Big Boss folded before Flop", out)

    def test_extract_blinds_handles_commas_short_allin_sb_and_dead_bb(self) -> None:
        comma_text = "Player1: posts small blind 1,000\nPlayer2: posts big blind 2,000\nPlayer1: posts the ante 250\n"
        self.assertEqual(extract_blinds_from_hand(comma_text), (1000, 2000, 250))

        short_sb = "Player1: posts small blind 20 and is all-in\nPlayer2: posts big blind 100\n*** HOLE CARDS ***\n"
        self.assertEqual(extract_blinds_from_hand(short_sb), (50, 100, None))

        dead_bb = "Player1: posts small blind 75\n*** HOLE CARDS ***\n"
        self.assertEqual(extract_blinds_from_hand(dead_bb), (75, 150, None))

    def test_detect_pp_hero_with_spaces(self) -> None:
        block = "Seat 1: Player1 (1000 in chips)\nSeat 2: Big Boss (1500 in chips)\nDealt to Big Boss [As Kd]\n"
        self.assertEqual(detect_pp_hero_token([block]), "Big Boss")


class OneWinBugFixTests(unittest.TestCase):
    def test_tournament_missing_sb_injects_chip_zero_not_dollar_and_hu_button_is_sb(self) -> None:
        raw = "\n".join(
            [
                "1WinPoker Hand #1001: Tournament (Daily Turbo)#555, 5 $ + 0.5 $ Hold'em No Limit - Level I (50/100) - 2026/09/01 14:00:00 UTC",
                "Table 'Turbo #1'(42) 2-max Seat #1 is the button",
                "Seat 1: Turbo (1000 in chips)",
                "Seat 2: Pot (1000 in chips)",
                "Pot: posts big blind 100",
                "*** HOLE CARDS ***",
                "Dealt to Turbo [As Ah]",
                "Turbo: raises 100 to 200",
                "Pot: folds",
                "Uncalled bet (100) returned to Turbo",
                "Turbo collected 200 from pot",
                "*** SUMMARY ***",
                "Total pot 200 | Rake 0",
                "Seat 1: Turbo (button) won (200)",
            ]
        )
        out = OneWinConverter().convert_hand(raw)
        # Tournament header & Total pot must NOT be corrupted by player names "Turbo" / "Pot".
        self.assertIn("$5+$0.5 Daily Turbo Hold'em", out)
        self.assertIn("Total pot 200 | Rake 0", out)
        # Heads-up: Button (Seat 1 = Turbo_1win) gets SB 0 (NOT $0, and NOT Seat 2).
        self.assertIn("Turbo_1win: posts small blind 0", out)
        self.assertNotIn("posts small blind $0", out)
        self.assertIn("Seat 1: Turbo_1win (button) collected (200)", out)


class GGUp888BugFixTests(unittest.TestCase):
    def test_gg_high_level_spaced_cashout_and_chat_won_preserved(self) -> None:
        raw = "\n".join(
            [
                "Poker Hand #TM5730000099: Tournament #123, $11 Main Hold'em No Limit - Level66(50000/100000) - 2026/08/17 18:00:00",
                "",
                "Table '12' 8-max Seat #1 is the button",
                "Seat 1: Hero (1000000 in chips)",
                "Big Fish: Chooses to EV Cashout",
                "*** HOLE CARDS ***",
                "Dealt to Opp [TAG]",
                "Dealt to Hero [Ah Kh]",
                'Hero said, "I won (100)"',
                "*** SUMMARY ***",
                "Seat 1: Hero won (200000)",
            ]
        )
        out = GGPokerConverter().convert_hand(raw)
        self.assertIn("- Level LXVI (50000/100000)", out)
        self.assertIn("Table 'GG_123 12' 8-max Seat #1 is the button", out)
        self.assertNotIn("EV Cashout", out)
        self.assertNotIn("Dealt to Opp [TAG]", out)
        self.assertIn('Hero said, "I won (100)"', out)
        self.assertIn("Seat 1: Hero collected (200000)", out)

    def test_up_preserves_chat_and_rewrites_table_after_blank_line(self) -> None:
        raw = "\n".join(
            [
                "Poker Hand #TM0ED70001: Tournament #1234567890123456789, $20 Daily Hold'em No Limit - Level 5 (100/200) - 2026/08/17 18:00:00 UTC",
                "",
                "Table '7' 8-max Seat #1 is the button",
                'Hero said, "I won (50)"',
                "Seat 1: Hero won (200)",
            ]
        )
        out = UPpokerConverter().convert_hand(raw)
        self.assertIn("Table '123456789 0' 8-max Seat #1 is the button", out)
        self.assertIn('Hero said, "I won (50)"', out)
        self.assertIn("Seat 1: Hero collected (200)", out)

    def test_888_pko_and_comma_buyin_meta(self) -> None:
        block = "\n".join(
            [
                "***** 888poker Hand History for Game 12345 ****",
                "$100/$200 Blinds No Limit Holdem - *** 15 08 2026 12:00:00",
                "Tournament #999 $5 + $5 + $1 Mystery Bounty - Table #1 8 Max (Real Money)",
            ]
        )
        tid, price, name, played = eight88_tournament_meta(block)
        self.assertEqual((tid, price, name, played), ("999", "$5+$5+$1", "Mystery Bounty", "2026-08-15"))


class ZipWatchEngineSettingsTests(unittest.TestCase):
    def test_zip_import_recognizes_888_hands_and_sanitizes_member_paths(self) -> None:
        hand_888 = "\n".join(
            [
                "#Game No : 55001",
                "***** 888poker Hand History for Game 55001 ****",
                "$10/$20 Blinds No Limit Holdem - *** 15 08 2026 12:00:00",
                "Tournament #1 $5 + $0.50 Daily - Table #1 8 Max (Real Money)",
            ]
        )
        with tempfile.TemporaryDirectory() as td:
            zpath = Path(td) / "hands.zip"
            out_dir = Path(td) / "out"
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("../../nested/888:test?.txt", hand_888)

            self.assertTrue(zip_looks_like_hand_history(zpath))
            members = classify_zip(zpath)
            self.assertEqual(len(members), 1)
            self.assertEqual(members[0].kind, "hands")
            self.assertEqual(members[0].room, "888poker")

            extracted = extract_zip_member(zpath, members[0].member_name, out_dir)
            self.assertEqual(extracted.parent.resolve(), out_dir.resolve())
            self.assertTrue(extracted.is_file())

    def test_zip_probe_ignores_macos_appledouble_entries(self) -> None:
        gg_hand = "Poker Hand #TM5730000001: Tournament #1, $5 Hold'em No Limit - Level1(10/20) - 2026/08/17 12:00:00\n"
        with tempfile.TemporaryDirectory() as td:
            zpath = Path(td) / "macos.zip"
            with zipfile.ZipFile(zpath, "w") as zf:
                for i in range(12):
                    zf.writestr(f"__MACOSX/._junk_{i}.txt", b"\x00\x05\x16\x07Mac OS X")
                zf.writestr("GG20260817-1.txt", gg_hand)
            self.assertTrue(zip_looks_like_hand_history(zpath))
            members = classify_zip(zpath)
            self.assertEqual([m.member_name for m in members], ["GG20260817-1.txt"])

    def test_select_new_files_does_not_false_match_suffix_and_prunes_by_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            target = folder / "table1.txt"
            target.write_text("hello", encoding="utf-8")
            os.utime(target, (1_000_000, 1_000_000))

            # Previously processed "2026_table1.txt" must NOT hide unrelated "table1.txt".
            state = FolderWatchState(
                processed_keys={"2026_table1.txt|5|2000000000000000"},
                freshest_mtime_ns=2_000_000_000_000_000,
            )
            found = select_new_files(folder, state, suffixes=(".txt",))
            self.assertEqual(found, [target])

            # Pruning >5000 keys must keep the newest entries by mtime, not alphabetically last.
            old_z_keys = {f"zzz_{i:04d}.txt|10|{i}" for i in range(4500)}
            new_a_keys = {f"aaa_{i:04d}.txt|10|{10_000_000 + i}" for i in range(600)}
            pruned = mark_processed(
                FolderWatchState(processed_keys=old_z_keys | new_a_keys, freshest_mtime_ns=0),
                [],
            )
            self.assertEqual(len(pruned.processed_keys), 4000)
            self.assertTrue(new_a_keys.issubset(pruned.processed_keys))

    def test_export_names_sanitizes_trailing_dots_and_accepts_omaha(self) -> None:
        meta = TournamentMeta("ggpoker_ok", "123", "$11", "Daily Bounty...", date(2026, 8, 17))
        self.assertEqual(export_filename(meta), "GG 2026-08-17 123 $11 Daily Bounty.txt")

        omaha_header = (
            "Poker Hand #TM5730000001: Tournament #555, $10 PLO Omaha Pot Limit "
            "- Level1(10/20) - 2026/08/17 12:00:00"
        )
        parsed = tournament_meta_from_blocks("ggpoker_ok", [omaha_header])
        self.assertEqual(parsed.tournament_id, "555")

    def test_dropbox_date_validation_rejects_impossible_months(self) -> None:
        cfg = default_settings()
        dest_dir, _ = _chico_dest(cfg, Path("2026_25_08_hands.txt"))
        self.assertEqual(dest_dir.name, "Misc")
        self.assertIsNone(_month_from_onewin_dropbox_name("1win_2026_25_08.txt"))
        self.assertEqual(_month_from_onewin_dropbox_name("1win_2026_08_25.txt"), 8)

    def test_process_all_appends_when_two_files_share_same_export_name(self) -> None:
        hand1 = "\n".join(
            [
                "Poker Hand #TM5730000001: Tournament #777, $11 Main Hold'em No Limit - Level1(10/20) - 2026/08/17 12:00:00",
                "Table '1' 6-max Seat #1 is the button",
                "Seat 1: Hero (1000 in chips)",
            ]
        )
        hand2 = "\n".join(
            [
                "Poker Hand #TM5730000002: Tournament #777, $11 Main Hold'em No Limit - Level1(10/20) - 2026/08/17 12:05:00",
                "Table '1' 6-max Seat #1 is the button",
                "Seat 1: Hero (1100 in chips)",
            ]
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            imp = root / "import"
            exp = root / "export"
            imp.mkdir()
            (imp / "part1.txt").write_text(hand1, encoding="utf-8")
            (imp / "part2.txt").write_text(hand2, encoding="utf-8")
            cfg = Settings(
                import_path=imp,
                export_path=exp,
                dropbox_base_path=Path(),
                chico_import_path=None,
                dropbox_mode="none",
                player_alias="MyHero",
                clear_import_after_convert=False,
                coin_as_ps=False,
                import_from_folders=False,
                poker_planets_folder=None,
                eight88_folder=None,
                onewin_folder=None,
                downloads_folder=None,
                clear_folders_after_import=False,
                ui_language="en",
            )
            state_file = root / "watch_state.json"
            with mock.patch("converter.import_state.import_state_path", return_value=state_file):
                process_all(cfg, console_print=False)

            exports = list(exp.glob("*.txt"))
            self.assertEqual(len(exports), 1)
            text = exports[0].read_text(encoding="utf-8")
            self.assertIn("205730000001", text)
            self.assertIn("205730000002", text)

    def test_settings_handles_corrupt_and_missing_keys_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "config.json"
            cfg_path.write_text("[1, 2, 3]", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_settings(cfg_path)

            cfg_path.write_text('{"import_path": "import"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_settings(cfg_path)

            # Saving over invalid JSON should succeed cleanly instead of raising.
            cfg_path.write_text("{broken json", encoding="utf-8")
            save_settings(cfg_path, default_settings())
            loaded = load_settings(cfg_path)
            self.assertEqual(loaded.player_alias, "Hero")


if __name__ == "__main__":
    unittest.main()
