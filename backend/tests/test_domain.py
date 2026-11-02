import unittest

from twitch_games.domain import (
    BankQuestion,
    InsufficientSupply,
    Mode,
    RoundPlan,
    Submission,
    accept_final_answer,
    eligible_random_modes,
    plan_reservation,
)


def bank(mode=Mode.NICHE, count=9, **overrides):
    values = dict(
        channel_id="channel", mode=mode, approved=True, source_eligible=True, off_cooldown=True
    )
    values.update(overrides)
    return [BankQuestion(id=f"{mode}-{i}", **values) for i in range(count)]


class ReservationTests(unittest.TestCase):
    def test_random_choices_exclude_previous(self):
        for previous in Mode:
            self.assertNotIn(previous, eligible_random_modes(previous))
            self.assertEqual(2, len(eligible_random_modes(previous)))
        with self.assertRaises(ValueError):
            plan_reservation("channel", [RoundPlan(Mode.NICHE, 3)] * 2, bank(), randomized=True)

    def test_unique_questions_across_rounds(self):
        source = bank() + bank(Mode.HIVE)
        plans = [RoundPlan(Mode.NICHE, 3), RoundPlan(Mode.HIVE, 4), RoundPlan(Mode.NICHE, 5)]
        result = plan_reservation("channel", plans, source, randomized=True)
        ids = [question for item in result for question in item.question_ids]
        self.assertEqual(12, len(ids))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(not q.reserved for q in source))

    def test_insufficiency_is_atomic(self):
        source = bank(count=3) + bank(Mode.HIVE, count=2)
        before = tuple(source)
        with self.assertRaises(InsufficientSupply):
            plan_reservation(
                "channel",
                [RoundPlan(Mode.NICHE, 3), RoundPlan(Mode.HIVE, 3)],
                source,
                randomized=True,
            )
        self.assertEqual(before, tuple(source))

    def test_ineligible_and_wrong_channel_supply_cannot_satisfy_start(self):
        for reason in [
            {"channel_id": "other"},
            {"approved": False},
            {"source_eligible": False},
            {"off_cooldown": False},
            {"reserved": True},
        ]:
            with self.subTest(reason=reason), self.assertRaises(InsufficientSupply):
                plan_reservation(
                    "channel", [RoundPlan(Mode.NICHE, 3)], bank(count=3, **reason), randomized=True
                )

    def test_duplicate_ids_rejected(self):
        source = bank(count=3)
        with self.assertRaises(ValueError):
            plan_reservation(
                "channel", [RoundPlan(Mode.NICHE, 3)], source + source, randomized=False
            )

    def test_count_bounds(self):
        for value in [0, 2, 6, True, 3.5]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                RoundPlan(Mode.NICHE, value)

    def test_exact_repeats_need_explicit_policy(self):
        rounds = [RoundPlan(Mode.NICHE, 3)] * 2
        for policy in [None, False]:
            with self.assertRaises(ValueError):
                plan_reservation(
                    "channel", rounds, bank(), randomized=False, allow_exact_repeats=policy
                )
        self.assertEqual(
            2,
            len(
                plan_reservation(
                    "channel", rounds, bank(), randomized=False, allow_exact_repeats=True
                )
            ),
        )

    def test_invalid_eligibility_types_rejected(self):
        for flag in ["false", 0, None]:
            with self.assertRaises(ValueError):
                bank(approved=flag)
        with self.assertRaises(ValueError):
            bank(mode="niche")
        with self.assertRaises(ValueError):
            plan_reservation("channel", [RoundPlan(Mode.NICHE, 3)], bank(), randomized="false")


class AnswerTests(unittest.TestCase):
    def test_first_and_identical_retry(self):
        accepted = Submission("q", "viewer", "spoon")
        self.assertIs(accepted, accept_final_answer(None, accepted))
        self.assertIs(accepted, accept_final_answer(accepted, Submission("q", "viewer", "spoon")))

    def test_revisions_and_mismatched_identity_rejected(self):
        accepted = Submission("q", "viewer", "spoon")
        for incoming in [Submission("q", "viewer", "fork"), Submission("q", "other", "spoon")]:
            with self.assertRaises(ValueError):
                accept_final_answer(accepted, incoming)

    def test_whitespace_rejected(self):
        with self.assertRaises(ValueError):
            accept_final_answer(None, Submission("q", "viewer", "  "))


if __name__ == "__main__":
    unittest.main()
