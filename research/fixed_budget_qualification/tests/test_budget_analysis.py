"""Independent numerical and pathwise checks of the paper's budget analysis."""

import itertools
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import budget_analysis as budget
from validate_method import classify, wilson_interval


class BudgetAnalysisTests(unittest.TestCase):
    def test_boundaries_match_wilson_including_strict_equalities(self):
        for b in range(1, 201):
            for epsilon in (.01, .05, .2, .5, .9):
                f, g = budget.boundaries(b, epsilon)
                for count in range(b + 1):
                    low, high = wilson_interval(count, b, budget.Z)
                    self.assertEqual(high < epsilon, count <= f)
                    self.assertEqual(low > epsilon, count >= g)
        # Exactly integral score boundaries must exclude equality on both sides.
        self.assertEqual(budget.boundaries(4, .5, 1), (0, 4))

    def test_first_budgets_against_independent_bernoulli_convolution(self):
        expected = {.01: { .8: 142, .9: 173}, .02: {.8: 311, .9: 389},
                    .03: {.8: 779, .9: 1012}}
        for q, targets in expected.items():
            mass = [1.0]
            crossings = {}
            for b in range(1, 1201):
                mass = ([mass[0] * (1-q)] +
                        [mass[k] * (1-q) + mass[k-1] * q for k in range(1, len(mass))] +
                        [mass[-1] * q])
                # Independent threshold determination from the Wilson interval.
                maximum = math.floor(b * .05)
                qualifying = [k for k in range(maximum + 1)
                              if wilson_interval(k, b, budget.Z)[1] < .05]
                probability = sum(mass[k] for k in qualifying)
                self.assertAlmostEqual(probability, budget.qualification_probability(b, q), places=11)
                for target in targets:
                    if target not in crossings and probability >= target:
                        crossings[target] = b
            self.assertEqual(crossings, targets)
            for target, b in targets.items():
                self.assertEqual(budget.first_budget(q, target), b)
        self.assertIsNone(budget.first_budget(.03, .9, ceiling=1000))
        self.assertLess(budget.qualification_probability(143, .02),
                        budget.qualification_probability(142, .02))

    def test_outcomes_and_cost_by_exhaustive_sequences(self):
        for b, epsilon in ((8, .5), (10, .5), (12, .3)):
            for q in (.2, .6):
                result = budget.operating_characteristics(b, q, epsilon, distributions=True)
                for mode in ("admission", "diagnostic"):
                    observed = [0.0] * (b + 1)
                    qualified = 0.0
                    for seq in itertools.product((0, 1), repeat=b):
                        total = sum(seq)
                        weight = q**total * (1-q)**(b-total)
                        truth = classify(total, b, epsilon, budget.Z)
                        count = 0
                        for n, x in enumerate(seq, 1):
                            count += x
                            record = budget.collection_result(b, n, count, mode, epsilon)
                            if record["status"] != "collecting":
                                break
                        observed[n] += weight
                        if record["classification"] == "qualify":
                            qualified += weight
                        if mode == "diagnostic":
                            self.assertEqual(record["classification"], truth)
                        elif record["status"] == "curtailed":
                            self.assertIsNone(record["classification"])
                            self.assertNotEqual(truth, "qualify")
                    self.assertAlmostEqual(qualified, result["full_budget_probabilities"]["qualify"])
                    for a, c in zip(observed, result["modes"][mode]["length_probabilities_0_to_B"]):
                        self.assertAlmostEqual(a, c)
                    self.assertAlmostEqual(sum(n*p for n, p in enumerate(observed)),
                                           result["modes"][mode]["expected_pairs"])

    def test_edge_cases_and_operational_records(self):
        for q, expected in ((0, (146, 146)), (1, (3, 13))):
            result = budget.operating_characteristics(146, q, distributions=True)
            for mode, cost in zip(("admission", "diagnostic"), expected):
                self.assertEqual(result["modes"][mode]["expected_pairs"], cost)
                self.assertAlmostEqual(sum(result["modes"][mode]["length_probabilities_0_to_B"]), 1)
        for mode in ("admission", "diagnostic"):
            self.assertEqual(budget.collection_result(10, 0, 0, mode)["status"], "infeasible")
            self.assertEqual(budget.operating_characteristics(10, .05)["modes"][mode]["expected_pairs"], 0)
            with self.assertRaises(ValueError):
                budget.collection_result(10, 1, 0, mode)
        self.assertEqual(budget.collection_result(146, 136, 3, "diagnostic")["status"], "collecting")
        self.assertEqual(budget.collection_result(146, 137, 3, "diagnostic")["classification"], "undecided")
        self.assertEqual(budget.collection_result(146, 146, 3, "admission")["classification"], "undecided")
        for args in ((0, .05, budget.Z), (146, 0, budget.Z), (146, .05, -1)):
            with self.assertRaises(ValueError):
                budget.boundaries(*args)

    def test_reported_costs_and_probability_mass(self):
        result = budget.operating_characteristics(146, .03, distributions=True)
        self.assertAlmostEqual(result["full_budget_probabilities"]["qualify"], .1831974876466122)
        self.assertAlmostEqual(result["modes"]["admission"]["expected_pairs"], 91.34953314651527)
        self.assertAlmostEqual(result["modes"]["diagnostic"]["expected_pairs"], 140.28003502646635)
        for n, q in ((1200, .99), (1200, .01), (100, .5)):
            mass = budget.binomial_mass(n, q)
            self.assertAlmostEqual(sum(mass), 1)
            self.assertAlmostEqual(sum(k*p for k, p in enumerate(mass)), n*q)


if __name__ == "__main__":
    unittest.main()
