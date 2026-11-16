"""Synthetic regression cases for CoinPoker action normalization (stdlib only)."""

import unittest

from converter.coin_convert import CoinPokerConverter
from converter.coin_format import coin_postprocess, normalize_coin_action_lines


class CoinAllInContributionTests(unittest.TestCase):
    def normalize(self, *lines: str) -> list[str]:
        return normalize_coin_action_lines(list(lines))

    def test_small_blind_allin_adds_the_already_posted_blind(self):
        result = self.normalize(
            "Alice: posts small blind 50",
            "Bob: posts big blind 100",
            "*** HOLE CARDS ***",
            "Alice: bets 950 and is all-in",
        )
        self.assertEqual(result[-1], "Alice: raises 900 to 1000 and is all-in")

    def test_big_blind_allin_adds_the_already_posted_blind(self):
        result = self.normalize(
            "Alice: posts small blind 50",
            "Bob: posts big blind 100",
            "*** HOLE CARDS ***",
            "Alice: raises 100 to 200",
            "Bob: bets 900 and is all-in",
        )
        self.assertEqual(result[-1], "Bob: raises 800 to 1000 and is all-in")

    def test_allin_adds_an_earlier_raise_on_the_same_street(self):
        result = self.normalize(
            "*** HOLE CARDS ***",
            "Alice: raises 4 to 6",
            "Bob: raises 10 to 16",
            "Alice: bets 34 and is all-in",
        )
        self.assertEqual(result[-1], "Alice: raises 24 to 40 and is all-in")

    def test_allin_adds_an_earlier_call_on_the_same_street(self):
        result = self.normalize(
            "*** HOLE CARDS ***",
            "Alice: calls 2",
            "Bob: raises 8 to 10",
            "Alice: bets 38 and is all-in",
        )
        self.assertEqual(result[-1], "Alice: raises 30 to 40 and is all-in")

    def test_postflop_allin_adds_an_earlier_bet(self):
        result = self.normalize(
            "*** FLOP *** [2c 7d Jh]",
            "Alice: bets 10",
            "Bob: raises 10 to 20",
            "Alice: bets 30 and is all-in",
        )
        self.assertEqual(result[-1], "Alice: raises 20 to 40 and is all-in")

    def test_short_allin_call_keeps_added_amount_and_highest_wager(self):
        result = self.normalize(
            "Alice: posts small blind 50",
            "Bob: posts big blind 100",
            "*** HOLE CARDS ***",
            "Bob: raises 400 to 500",
            "Alice: bets 150 and is all-in",
            "Cara: bets 300 and is all-in",
        )
        self.assertEqual(result[-2:], [
            "Alice: calls 150 and is all-in",
            "Cara: calls 300 and is all-in",
        ])

    def test_first_preflop_short_allin_remains_a_call_of_the_blind(self):
        result = self.normalize(
            "Alice: posts small blind 50",
            "Bob: posts big blind 100",
            "*** HOLE CARDS ***",
            "Alice: bets 25 and is all-in",
        )
        self.assertEqual(result[-1], "Alice: calls 25 and is all-in")

    def test_allin_equal_to_wager_after_prior_call_is_a_call(self):
        result = self.normalize(
            "*** FLOP *** [2c 7d Jh]",
            "Bob: bets 10",
            "Alice: calls 10",
            "Bob: raises 15 to 25",
            "Alice: bets 15 and is all-in",
        )
        self.assertEqual(result[-1], "Alice: calls 15 and is all-in")

    def test_new_street_resets_player_contributions_and_wager(self):
        result = self.normalize(
            "Alice: posts small blind 50",
            "Bob: posts big blind 100",
            "*** HOLE CARDS ***",
            "Alice: calls 50",
            "*** FLOP *** [2c 7d Jh]",
            "Alice: bets 20 and is all-in",
            "*** TURN *** [2c 7d Jh] [4s]",
            "Bob: bets 10 and is all-in",
        )
        self.assertEqual(result[-3], "Alice: bets 20 and is all-in")
        self.assertEqual(result[-1], "Bob: bets 10 and is all-in")

    def test_ante_is_not_part_of_the_street_commitment(self):
        result = self.normalize(
            "Alice: posts the ante 10",
            "Bob: posts the ante 10",
            "Alice: posts small blind 50",
            "Bob: posts big blind 100",
            "*** HOLE CARDS ***",
            "Alice: bets 950 and is all-in",
        )
        self.assertEqual(result[-1], "Alice: raises 900 to 1000 and is all-in")

    def test_return_reduces_commitment_before_a_later_allin(self):
        result = self.normalize(
            "*** FLOP *** [2c 7d Jh]",
            "Alice: bets 40",
            "Bob: calls 10",
            "Uncalled bet (30) returned to Alice",
            "Alice: bets 15 and is all-in",
        )
        self.assertEqual(result[-1], "Alice: raises 15 to 25 and is all-in")

    def test_cash_symbols_and_decimal_blinds_are_preserved(self):
        result = self.normalize(
            "Alice: posts small blind $0.25",
            "Bob: posts big blind $0.50",
            "*** HOLE CARDS ***",
            "Alice: bets $9.75 and is all-in",
        )
        self.assertEqual(result[-1], "Alice: raises $9.5 to $10 and is all-in")

    def test_ordinary_opening_bets_and_existing_raises_stay_unchanged(self):
        lines = [
            "*** FLOP *** [2c 7d Jh]",
            "Alice: bets 10.25",
            "Bob: calls 10.25",
            "Alice: raises 20 to 30.25",
            "*** TURN *** [2c 7d Jh] [4s]",
            "Bob: bets 20",
        ]
        self.assertEqual(self.normalize(*lines), lines)


class CoinPostprocessTests(unittest.TestCase):
    def test_short_bb_runout_is_rewritten_for_h2n(self):
        hand = "\n".join(
            [
                "PokerStars Hand #1: Tournament #1, Hold'em No Limit - Level (350/700) - 2026/01/01 0:00:00 UTC",
                "Table 'CPR_1 0' 6-max Seat #1 is the button",
                "Seat 1: SB (1000 in chips)",
                "Seat 2: BB (49 in chips)",
                "SB: posts the ante 10",
                "BB: posts the ante 10",
                "SB: posts small blind 350",
                "BB: posts big blind 49 and is all-in",
                "*** HOLE CARDS ***",
                "Dealt to SB [Ah Kh]",
                "Uncalled bet (301) returned to SB",
                "*** FLOP *** [2c 7d Jh]",
                "*** TURN *** [2c 7d Jh] [4s]",
                "*** RIVER *** [2c 7d Jh 4s] [9c]",
                "*** SHOW DOWN ***",
                "BB: shows [2d 2s] (One Pair)",
                "SB: shows [Ah Kh] (High Card)",
                "BB collected 118 from pot",
                "*** SUMMARY ***",
                "Total pot 118 | Rake 0",
            ]
        )
        out = coin_postprocess(hand)
        self.assertIn("SB: posts small blind 49", out)
        self.assertIn("BB: posts big blind 49 and is all-in", out)
        self.assertIn("SB: checks", out)
        self.assertNotIn("Uncalled bet", out)

    def test_cpr_postprocess_integerizes_and_strips_unshown_showdown(self):
        """Hand2NoteHh Coin file format: integer chips, no SHOW DOWN without shows."""
        hand = "\n".join(
            [
                "PokerStars Hand #2: Tournament #2, Hold'em No Limit - Level (200/400) - 2026/01/01 0:00:00 UTC",
                "Table 'CPR_2 0' 7-max Seat #1 is the button",
                "Seat 1: Alice (20060.07 in chips)",
                "Seat 2: Bob (19811.49 in chips)",
                "Alice: posts the ante 60",
                "Bob: posts the ante 60",
                "Alice: posts small blind 200",
                "Bob: posts big blind 400",
                "*** HOLE CARDS ***",
                "Dealt to Alice [Ks 6h]",
                "Alice: raises 400 to 800",
                "Bob: folds",
                "Uncalled bet (400) returned to Alice",
                "*** SHOW DOWN ***",
                "Alice collected 720 from pot",
                "*** SUMMARY ***",
                "Total pot 720 | Rake 0",
            ]
        )
        out = coin_postprocess(hand)
        self.assertIn("Alice (20060 in chips)", out)
        self.assertNotIn("*** SHOW DOWN ***", out)
        self.assertIn("Alice collected 720 from pot", out)

    def test_coinpoker_room_vs_pokerstars_room_layouts(self):
        raw = "\n".join(
            [
                "CoinPoker Hand #137369300026: NLH (120/240/30) 2026/08/17 18:03:42 +05",
                "Tournament '$88 CoinMasters Asia - DOGE' '89453' 7-max Seat #2 is the button",
                "Seat 1: cc7178c8 (17,820.75 in chips)",
                "Seat 3: 9bbe904a (23,323.65 in chips)",
                "Seat 4: 5351e524 (16,843.86 in chips)",
                "Seat 5: Hero (20,080.14 in chips)",
                "cc7178c8: posts ante 30",
                "9bbe904a: posts ante 30",
                "5351e524: posts ante 30",
                "Hero: posts ante 30",
                "9bbe904a: posts small blind 120",
                "5351e524: posts big blind 240",
                "*** HOLE CARDS ***",
                "Dealt to Hero [7c 6h]",
                "Hero: folds",
                "cc7178c8: folds",
                "9bbe904a: raises 600 to 840",
                "5351e524: calls 600",
                "*** FLOP *** [Ac Qd 7h]",
                "9bbe904a: bets 472.50",
                "5351e524: folds",
                "9bbe904a: RETURN 472.50",
                "*** SHOWDOWN ***",
                "9bbe904a collected 1,890 from pot",
                "*** SUMMARY ***",
                "Total pot 1,890",
                "Board [ Ac Qd 7h ]",
                "Seat 3: 9bbe904a won (1,890)",
                "Seat 5: Hero folded before Flop (didn't bet)",
            ]
        )
        cpr = CoinPokerConverter("klicker1979", coin_as_ps=False).convert_hand(raw)
        # Hybrid: full PS body (Level I, 33-prefix, decimals) + CPR_ table tag only.
        self.assertIn("PokerStars Hand #33137369300026:", cpr)
        self.assertIn("Table 'CPR_89453 1'", cpr)
        self.assertIn("Level I (120/240(30))", cpr)
        self.assertIn("posts big blind 240", cpr)
        self.assertIn("(17820.75 in chips)", cpr)
        self.assertIn("bets 472.50", cpr)
        self.assertNotIn("€", cpr)
        self.assertIn("*** SHOW DOWN ***", cpr)
        self.assertIn("Dealt to klicker1979 [", cpr)
        self.assertNotIn("_coin", cpr)

        ps = CoinPokerConverter("klicker1979", coin_as_ps=True).convert_hand(raw)
        self.assertIn("PokerStars Hand #33137369300026:", ps)
        self.assertIn("Table '89453 1'", ps)
        self.assertIn("Level I (120/240(30))", ps)
        self.assertIn("bets 472.50", ps)
        self.assertNotIn("CPR_", ps)
        self.assertIn("*** SHOW DOWN ***", ps)
        self.assertIn("Dealt to klicker1979_coin [", ps)

    def test_blind_and_ante_allin_posts_omit_allin_flag(self):
        raw = "\n".join(
            [
                "CoinPoker Hand #199197900004: NLH (350/700/88) 2026/10/05 23:12:09 +03",
                "Tournament '$11 Test' '108844' 6-max Seat #4 is the button",
                "Seat 5: aaaaaaaa (1000 in chips)",
                "Seat 6: bbbbbbbb (49 in chips)",
                "Seat 1: Hero (2000 in chips)",
                "aaaaaaaa: posts ante 88",
                "bbbbbbbb: posts ante 49 ALLIN",
                "Hero: posts ante 88",
                "aaaaaaaa: posts small blind 350",
                "bbbbbbbb: posts big blind 49 ALLIN",
                "*** HOLE CARDS ***",
                "Dealt to Hero [9h 4h]",
                "Hero: folds",
                "aaaaaaaa: folds",
                "bbbbbbbb: RETURN 0",
                "*** SHOWDOWN ***",
                "bbbbbbbb collected 100 from pot",
                "*** SUMMARY ***",
                "Total pot 100",
                "Board [ ]",
                "Seat 6: bbbbbbbb won (100)",
            ]
        )
        for as_ps in (False, True):
            out = CoinPokerConverter("hero", coin_as_ps=as_ps).convert_hand(raw)
            self.assertNotIn("posts big blind 49 and is all-in", out)
            self.assertNotIn("posts the ante 49 and is all-in", out)
            self.assertIn("bbbbbbbb: posts big blind 49", out)


if __name__ == "__main__":
    unittest.main()
