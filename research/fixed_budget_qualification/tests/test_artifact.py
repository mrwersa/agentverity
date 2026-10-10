from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import analyse_maintenance
import validate_method


class MaintenanceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = analyse_maintenance.load_input(ROOT / "maintenance_input.json")
        cls.result = analyse_maintenance.analyse(cls.payload)

    def test_reported_aggregate_is_reproduced(self) -> None:
        self.assertEqual(self.result["derived_input_inconsistencies"], 0)
        self.assertEqual(self.result["overall"]["cells"], 40)
        self.assertEqual(self.result["overall"]["stops"], 2)
        self.assertEqual(self.result["overall"]["multi_disagreement_stops"], 2)
        self.assertEqual(self.result["overall"]["pairs_saved"], 233)
        self.assertAlmostEqual(self.result["overall"]["saved_share"], 233 / 5840)
        self.assertEqual(self.result["overall"]["stopped_pairs_planned"], 292)
        self.assertAlmostEqual(
            self.result["overall"]["saved_share_when_stopped"], 233 / 292
        )

    def test_configuration_rows_match_the_anonymised_table_order(self) -> None:
        rows = self.result["by_configuration"]
        names = ("C1", "C2", "C3", "C4")
        self.assertEqual([rows[name]["stops"] for name in names], [1, 1, 0, 0])
        self.assertEqual(
            [rows[name]["multi_disagreement_stops"] for name in names],
            [1, 1, 0, 0],
        )
        self.assertEqual([rows[name]["pairs_saved"] for name in names], [91, 142, 0, 0])
        self.assertEqual(
            [rows[name]["final_classifications"] for name in names],
            [
                {"qualify": 9, "undecided": 1},
                {"qualify": 9, "exceeds_tolerance": 1},
                {"qualify": 10},
                {"qualify": 10},
            ],
        )

    def test_inconsistent_final_disagreement_count_is_rejected(self) -> None:
        malformed = copy.deepcopy(self.payload)
        malformed["cells"][0]["final_disagreements"] = 3
        with self.assertRaisesRegex(
            ValueError, "conflicts with final disagreement count"
        ):
            analyse_maintenance.analyse(malformed)

    def test_exceeds_tolerance_cannot_be_relabelled_undecided(self) -> None:
        malformed = copy.deepcopy(self.payload)
        above_tolerance = next(
            cell
            for cell in malformed["cells"]
            if cell["final_classification"] == "exceeds_tolerance"
        )
        above_tolerance["final_classification"] = "undecided"
        with self.assertRaisesRegex(
            ValueError, "conflicts with final disagreement count"
        ):
            analyse_maintenance.analyse(malformed)

    def test_stopping_count_must_cross_the_endpoint_boundary(self) -> None:
        malformed = copy.deepcopy(self.payload)
        stopped = next(cell for cell in malformed["cells"] if cell["stop_pair"])
        stopped["disagreements_at_stop"] = 2
        with self.assertRaisesRegex(ValueError, "does not cross"):
            analyse_maintenance.analyse(malformed)

    def test_committed_maintenance_result_is_current(self) -> None:
        expected = json.dumps(self.result, indent=2, sort_keys=True) + "\n"
        self.assertEqual((ROOT / "maintenance_results.json").read_text(), expected)


class MethodTests(unittest.TestCase):
    def test_disagreement_limit_matches_wilson_classification(self) -> None:
        z = validate_method.NormalDist().inv_cdf(0.975)
        for epsilon in (0.01, 0.05, 0.20):
            for pairs in range(1, 301):
                limit = validate_method.maximum_qualifying_disagreements(
                    pairs, epsilon, z
                )
                for disagreements in range(pairs + 1):
                    outcome = validate_method.classify(disagreements, pairs, epsilon, z)
                    self.assertEqual(outcome == "qualify", disagreements <= limit)

    def test_minimum_qualifying_budget_matches_brute_force(self) -> None:
        z = validate_method.NormalDist().inv_cdf(0.975)
        for epsilon in (0.01, 0.05, 0.20):
            for disagreements in range(11):
                budget = validate_method.minimum_qualifying_budget(disagreements, epsilon, z)
                self.assertEqual(
                    validate_method.classify(disagreements, budget, epsilon, z), "qualify"
                )
                if budget > max(disagreements, 1):
                    self.assertNotEqual(
                        validate_method.classify(
                            disagreements, budget - 1, epsilon, z
                        ),
                        "qualify",
                    )

    def test_wilson_zero_disagreement_minimum_is_73_pairs(self) -> None:
        z = validate_method.NormalDist().inv_cdf(0.975)
        self.assertGreaterEqual(validate_method.wilson_interval(0, 72, z)[1], 0.05)
        self.assertLess(validate_method.wilson_interval(0, 73, z)[1], 0.05)

    def test_nonzero_disagreement_curtailment_example(self) -> None:
        z = validate_method.NormalDist().inv_cdf(0.975)
        self.assertLess(validate_method.wilson_interval(2, 146, z)[1], 0.05)
        self.assertGreaterEqual(validate_method.wilson_interval(3, 146, z)[1], 0.05)
        self.assertGreaterEqual(validate_method.wilson_interval(3, 172, z)[1], 0.05)
        self.assertLess(validate_method.wilson_interval(3, 173, z)[1], 0.05)

    def test_small_simulation_is_seed_reproducible(self) -> None:
        options = {
            "trials": 100,
            "seed": 41,
            "rates": (0.05,),
            "correlations": (0.0, 0.1),
        }
        self.assertEqual(validate_method.simulate(**options), validate_method.simulate(**options))

    def test_exact_boundary_matches_the_reported_value(self) -> None:
        result = validate_method.simulate(
            trials=10, rates=(0.05,), correlations=(0.0,)
        )
        rate = result["exact_boundary"][
            "incorrect_directional_classification_probability"
        ]
        self.assertGreater(rate, 0.0528)
        self.assertLess(rate, 0.0529)

    def test_exact_maintenance_boundary_matches_the_reported_value(self) -> None:
        z = validate_method.NormalDist().inv_cdf(0.975)
        row = validate_method.exact_boundary(146, 0.05, z, 0.10)
        self.assertAlmostEqual(row["outcomes"]["qualify"], 0.46192766, places=7)
        self.assertAlmostEqual(
            row["outcomes"]["exceeds_tolerance"], 0.20072288, places=7
        )
        self.assertAlmostEqual(
            row["incorrect_directional_classification_probability"],
            0.66265054,
            places=7,
        )

    def test_off_boundary_dependence_matches_the_reported_values(self) -> None:
        z = validate_method.NormalDist().inv_cdf(0.975)
        short = validate_method.exact_classification(146, 0.03, 0.05, z, 0.10)
        long = validate_method.exact_classification(2_000, 0.03, 0.05, z, 0.10)
        self.assertAlmostEqual(
            short["outcomes"]["exceeds_tolerance"], 0.11186351, places=7
        )
        self.assertAlmostEqual(
            long["outcomes"]["exceeds_tolerance"], 0.16206542, places=7
        )

    def test_render_separates_exact_boundary_from_monte_carlo(self) -> None:
        result = validate_method.simulate(
            trials=10, rates=(0.05,), correlations=(0.0, 0.10)
        )
        rendered = validate_method.render(result)
        exact = result["exact_boundary"]
        self.assertIn("exact iid boundary (p = epsilon)", rendered)
        self.assertIn(
            "incorrect "
            f"{exact['incorrect_directional_classification_probability']:.3%}",
            rendered,
        )
        self.assertIn("  146  0.10", rendered)

    def test_reported_validation_rejects_an_incomplete_result(self) -> None:
        result = validate_method.simulate(
            trials=10, rates=(0.05,), correlations=(0.0,)
        )
        with self.assertRaisesRegex(ValueError, "missing boundary sensitivity row"):
            validate_method.validate_reported(result)

if __name__ == "__main__":
    unittest.main()
