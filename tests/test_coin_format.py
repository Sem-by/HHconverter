"""Synthetic regression cases for CoinPoker action normalization (stdlib only)."""

import unittest

from converter.coin_format import normalize_coin_action_lines


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


if __name__ == "__main__":
    unittest.main()
