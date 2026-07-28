"""Tests for declared decision contracts and structured suites."""

from __future__ import annotations

import json

import pytest

from agentverity import from_callable, run
from agentverity.decision_contract import (
    DECISION_SUITE_SCHEMA,
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    assess_decision_coverage,
    load_decision_suite,
    save_decision_suite,
)
from agentverity.runner import RunConfig


def _suite() -> DecisionSuite:
    return DecisionSuite(
        contract=DecisionContract(
            allowed={"billing", "refund", "fraud", "other"},
            required={"billing", "refund", "fraud"},
            critical={"fraud"},
        ),
        cases=(
            DecisionCase("charged twice", "billing"),
            DecisionCase("refund missing", "refund"),
            DecisionCase("not my purchase", "fraud"),
        ),
    )


def test_contract_defaults_required_to_allowed_and_normalises_sets():
    contract = DecisionContract(allowed=["allow", "deny"])

    assert contract.allowed == frozenset({"allow", "deny"})
    assert contract.required == contract.allowed
    assert contract.critical == frozenset()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"allowed": []}, "allowed must contain"),
        (
            {"allowed": {"allow"}, "required": {"deny"}},
            "required decisions are not allowed",
        ),
        (
            {
                "allowed": {"allow", "deny"},
                "required": {"allow"},
                "critical": {"deny"},
            },
            "critical decisions must also be required",
        ),
    ],
)
def test_contract_rejects_incoherent_sets(kwargs, message):
    with pytest.raises(ValueError, match=message):
        DecisionContract(**kwargs)


@pytest.mark.parametrize(
    "allowed",
    ["allow", 42, {"allow", ""}],
)
def test_contract_rejects_malformed_label_collections(allowed):
    with pytest.raises((TypeError, ValueError)):
        DecisionContract(allowed=allowed)


def test_contract_from_dict_rejects_wrong_shape_and_missing_allowed():
    with pytest.raises(TypeError, match="must be an object"):
        DecisionContract.from_dict([])
    with pytest.raises(ValueError, match="missing 'allowed'"):
        DecisionContract.from_dict({})


def test_case_and_suite_reject_malformed_values():
    contract = DecisionContract(allowed={"allow"})
    with pytest.raises(ValueError, match="case input"):
        DecisionCase("", "allow")
    with pytest.raises(ValueError, match="expected decision"):
        DecisionCase("x", "")
    with pytest.raises(ValueError, match="at least one case"):
        DecisionSuite(contract=contract, cases=())
    with pytest.raises(TypeError, match="DecisionCase"):
        DecisionSuite(contract=contract, cases=("x",))
    with pytest.raises(TypeError, match="DecisionContract"):
        DecisionSuite(contract={}, cases=(DecisionCase("x", "allow"),))


def test_suite_rejects_unknown_expectation_and_duplicate_inputs():
    contract = DecisionContract(allowed={"allow", "deny"})
    with pytest.raises(ValueError, match="outside the allowed"):
        DecisionSuite(
            contract=contract,
            cases=(DecisionCase("x", "review"),),
        )
    with pytest.raises(ValueError, match="duplicate"):
        DecisionSuite(
            contract=contract,
            cases=(
                DecisionCase("same", "allow"),
                DecisionCase("same", "deny"),
            ),
        )


def test_suite_round_trip_is_versioned(tmp_path):
    path = tmp_path / "suite.json"
    save_decision_suite(_suite(), path)
    payload = json.loads(path.read_text())

    assert payload["schema"] == DECISION_SUITE_SCHEMA
    assert load_decision_suite(path) == _suite()


def test_suite_loader_rejects_invalid_files(tmp_path):
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{")
    with pytest.raises(ValueError, match="cannot load"):
        load_decision_suite(invalid_json)

    with pytest.raises(TypeError, match="root must be an object"):
        DecisionSuite.from_dict([])
    with pytest.raises(ValueError, match="unsupported"):
        DecisionSuite.from_dict({"schema": "future"})
    with pytest.raises(TypeError, match="cases must be a list"):
        DecisionSuite.from_dict(
            {
                "schema": DECISION_SUITE_SCHEMA,
                "contract": {"allowed": ["allow"]},
                "cases": "wrong",
            }
        )


def test_assessment_separates_intended_observed_and_unknown_decisions():
    suite = _suite()
    result = assess_decision_coverage(
        suite,
        ("billing", "other", "invented"),
    )

    assert result.intended_coverage == 1.0
    assert result.observed_coverage == pytest.approx(1 / 3)
    assert result.missing_intended == ()
    assert result.missing_observed == ("fraud", "refund")
    assert result.missing_critical == ("fraud",)
    assert result.unknown_observed == ("invented",)
    assert result.satisfied is False


def test_assessment_detects_unknown_label_from_a_repeat_without_inflating_counts():
    suite = _suite()
    result = assess_decision_coverage(
        suite,
        ("billing", "refund", "fraud"),
        all_observed=(
            "billing",
            "billing",
            "refund",
            "invented",
            "fraud",
            "fraud",
        ),
    )

    assert result.observed_coverage == 1.0
    assert tuple(item.count for item in result.observed_counts) == (1, 1, 1)
    assert result.unknown_observed == ("invented",)
    assert not result.satisfied


def test_assessment_reports_missing_cases_before_model_behaviour():
    suite = DecisionSuite(
        contract=DecisionContract(allowed={"allow", "review", "deny"}),
        cases=(
            DecisionCase("safe", "allow"),
            DecisionCase("unsafe", "deny"),
        ),
    )
    result = assess_decision_coverage(suite, ("allow", "deny"))

    assert result.missing_intended == ("review",)
    assert result.advice.startswith("add reviewed cases")


def test_assessment_is_satisfied_without_scoring_case_correctness():
    suite = _suite()
    # The labels are deliberately permuted. Coverage is complete, while a
    # correctness evaluator must still reject the individual routes.
    result = assess_decision_coverage(
        suite,
        ("refund", "fraud", "billing"),
    )

    assert result.satisfied is True
    assert result.intended_coverage == 1.0
    assert result.observed_coverage == 1.0


def test_runner_reports_a_satisfied_contract_without_changing_quality_ownership():
    suite = _suite()
    by_input = {
        "charged twice": "billing",
        "refund missing": "refund",
        "not my purchase": "fraud",
    }
    result = run(
        from_callable(lambda text: {"verdict": by_input[text]}),
        suite=suite,
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )

    assert result.status == "deterministic"
    assert result.decision_coverage is not None
    assert result.decision_coverage.satisfied
    assert "all 3 required decisions" in result.headline
    assert "DECLARED DECISION CONTRACT" in result.summary()


def test_runner_detects_out_of_contract_label_on_a_repeat():
    suite = _suite()
    expected = {
        "charged twice": "billing",
        "refund missing": "refund",
        "not my purchase": "fraud",
    }
    calls: dict[str, int] = {}

    def route(text: str) -> dict[str, str]:
        calls[text] = calls.get(text, 0) + 1
        verdict = (
            "invented"
            if text == "charged twice" and calls[text] == 2
            else expected[text]
        )
        return {"verdict": verdict}

    result = run(
        from_callable(route),
        suite=suite,
        relations=[],
        config=RunConfig(k=4, epsilon=0.9),
    )

    assert result.decision_coverage is not None
    assert result.decision_coverage.observed_coverage == 1.0
    assert result.decision_coverage.unknown_observed == ("invented",)
    assert result.status == "contract"


def test_runner_contract_failure_precedes_generic_blindness():
    suite = DecisionSuite(
        contract=DecisionContract(allowed={"allow", "review", "deny"}),
        cases=(
            DecisionCase("safe", "allow"),
            DecisionCase("unsafe", "deny"),
        ),
    )
    result = run(
        from_callable(lambda text: {"verdict": "allow" if text == "safe" else "deny"}),
        suite=suite,
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )

    assert result.status == "contract"
    assert result.decision_coverage is not None
    assert result.decision_coverage.missing_intended == ("review",)
    assert "add reviewed cases" in result.headline


def test_runner_rejects_ambiguous_input_source_and_wrong_layer():
    suite = _suite()
    agent = from_callable(lambda text: {"verdict": text})

    with pytest.raises(ValueError, match="exactly one"):
        run(agent)
    with pytest.raises(ValueError, match="exactly one"):
        run(agent, ["x"], suite=suite)
    with pytest.raises(ValueError, match="verdict observation layer"):
        run(
            agent,
            suite=suite,
            relations=[],
            config=RunConfig(layer="tools"),
        )


def test_existing_generator_inputs_are_consumed_once():
    inputs = (value for value in ("a", "b"))
    result = run(
        from_callable(lambda text: {"verdict": text}),
        inputs,
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )

    assert result.requested_inputs == 2


class TestLoadingReportsMalformedSuitesConsistently:
    """A loader with two error types makes callers write two except clauses,
    so every malformed suite file has to surface as ValueError."""

    @staticmethod
    def _write(tmp_path, payload):
        path = tmp_path / "suite.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_a_missing_contract_is_a_value_error(self, tmp_path):
        path = self._write(
            tmp_path,
            {
                "schema": DECISION_SUITE_SCHEMA,
                "cases": [{"input": "x", "expected": "a"}],
            },
        )
        with pytest.raises(ValueError, match="missing 'contract'"):
            load_decision_suite(path)

    def test_a_contract_without_allowed_is_a_value_error(self, tmp_path):
        path = self._write(
            tmp_path,
            {
                "schema": DECISION_SUITE_SCHEMA,
                "contract": {},
                "cases": [{"input": "x", "expected": "a"}],
            },
        )
        with pytest.raises(ValueError, match="missing 'allowed'"):
            load_decision_suite(path)

    def test_a_case_missing_a_key_is_a_value_error(self, tmp_path):
        path = self._write(
            tmp_path,
            {
                "schema": DECISION_SUITE_SCHEMA,
                "contract": {"allowed": ["a"]},
                "cases": [{"input": "x"}],
            },
        )
        with pytest.raises(ValueError, match="invalid decision case"):
            load_decision_suite(path)

    def test_a_non_object_case_is_a_value_error(self, tmp_path):
        path = self._write(
            tmp_path,
            {
                "schema": DECISION_SUITE_SCHEMA,
                "contract": {"allowed": ["a"]},
                "cases": ["not an object"],
            },
        )
        with pytest.raises(ValueError, match="invalid decision case"):
            load_decision_suite(path)

    @pytest.mark.parametrize(
        ("payload", "message"),
        [
            ([], "decision suite root must be an object"),
            (
                {
                    "schema": DECISION_SUITE_SCHEMA,
                    "contract": [],
                    "cases": [],
                },
                "decision contract must be an object",
            ),
            (
                {
                    "schema": DECISION_SUITE_SCHEMA,
                    "contract": {"allowed": ["a"]},
                    "cases": {},
                },
                "decision suite cases must be a list",
            ),
            (
                {
                    "schema": DECISION_SUITE_SCHEMA,
                    "contract": {"allowed": "a"},
                    "cases": [{"input": "x", "expected": "a"}],
                },
                "allowed must be a collection",
            ),
        ],
    )
    def test_every_malformed_file_has_one_error_contract(
        self, tmp_path, payload, message
    ):
        path = self._write(tmp_path, payload)

        with pytest.raises(ValueError, match=message):
            load_decision_suite(path)

    def test_from_dict_still_rejects_a_non_object_contract_by_type(self):
        """Handing the wrong kind of object straight to from_dict is a
        programming error, so it keeps raising TypeError."""
        with pytest.raises(TypeError, match="must be an object"):
            DecisionContract.from_dict(["allowed"])


def test_an_empty_required_set_is_rejected():
    with pytest.raises(ValueError, match="required must contain at least one"):
        DecisionContract(allowed={"approve"}, required=set())


def test_missing_required_cases_lists_routes_with_no_case():
    suite = DecisionSuite(
        contract=DecisionContract(allowed={"approve", "review", "deny"}),
        cases=(DecisionCase("routine", "approve"),),
    )

    assert suite.missing_required_cases == ("deny", "review")


def test_observed_decisions_must_align_with_the_suite():
    suite = DecisionSuite(
        contract=DecisionContract(allowed={"approve"}),
        cases=(DecisionCase("routine", "approve"),),
    )

    with pytest.raises(ValueError, match="align with decision suite cases"):
        assess_decision_coverage(suite, ("approve", "approve"))


class TestAdviceNamesTheNextAction:
    """The advice string is what a reader acts on, so each branch is pinned."""

    suite = DecisionSuite(
        contract=DecisionContract(allowed={"approve", "deny"}),
        cases=(DecisionCase("routine", "approve"), DecisionCase("bad", "deny")),
    )

    def test_an_out_of_contract_label_is_named(self):
        result = assess_decision_coverage(self.suite, ("approve", "escalate"))

        assert result.satisfied is False
        assert result.advice == (
            "the agent emitted decisions outside the contract: escalate"
        )

    def test_a_required_route_that_never_returned_is_named(self):
        result = assess_decision_coverage(self.suite, ("approve", None))

        assert result.satisfied is False
        assert result.advice == (
            "required decisions were represented by cases but not returned: deny"
        )

    def test_an_out_of_contract_label_outranks_a_missing_route(self):
        """Both are wrong, but a label outside the contract is the more
        urgent repair because it means the contract is stale."""
        result = assess_decision_coverage(self.suite, ("escalate", None))

        assert "outside the contract" in result.advice

    def test_a_complete_run_says_so(self):
        result = assess_decision_coverage(self.suite, ("approve", "deny"))

        assert result.satisfied is True
        assert result.advice == "all required decisions were represented and observed"


class TestStabilityTargets:
    """Risk labels and numerical stability policy stay separate."""

    def test_a_target_overrides_the_run_default_for_that_route_only(self):
        contract = DecisionContract(
            allowed={"approve", "deny"},
            critical={"deny"},
            stability_targets={"deny": 0.01},
        )
        assert contract.target_for("deny", 0.05) == 0.01
        assert contract.target_for("approve", 0.05) == 0.05

    def test_a_target_for_an_unknown_decision_is_rejected(self):
        with pytest.raises(ValueError, match="not required"):
            DecisionContract(allowed={"approve"}, stability_targets={"deny": 0.01})

    def test_a_target_for_an_optional_decision_is_rejected(self):
        with pytest.raises(ValueError, match="not required"):
            DecisionContract(
                allowed={"approve", "review"},
                required={"approve"},
                stability_targets={"review": 0.05},
            )

    @pytest.mark.parametrize("bad", [0, 1, -0.1, 1.5])
    def test_a_target_outside_zero_to_one_is_rejected(self, bad):
        with pytest.raises(ValueError, match="between 0 and 1"):
            DecisionContract(allowed={"approve"}, stability_targets={"approve": bad})

    @pytest.mark.parametrize("bad", ["0.01", True, None])
    def test_a_non_numeric_target_is_rejected(self, bad):
        with pytest.raises(TypeError, match="must be a number"):
            DecisionContract(allowed={"approve"}, stability_targets={"approve": bad})

    def test_targets_must_be_a_mapping(self):
        with pytest.raises(TypeError, match="must be a mapping"):
            DecisionContract(allowed={"approve"}, stability_targets=["approve"])

    def test_targets_survive_a_round_trip(self):
        contract = DecisionContract(
            allowed={"approve", "deny"}, stability_targets={"deny": 0.01}
        )
        assert DecisionContract.from_dict(contract.to_dict()).stability_targets == {
            "deny": 0.01
        }

    def test_a_contract_without_targets_omits_the_key(self):
        contract = DecisionContract(allowed={"approve"})
        assert "stability_targets" not in contract.to_dict()
        assert contract.stability_targets == {}

    def test_targets_cannot_mutate_a_frozen_contract(self):
        contract = DecisionContract(
            allowed={"approve", "deny"},
            stability_targets={"deny": 0.01},
        )
        with pytest.raises(TypeError):
            contract.stability_targets["deny"] = 0.5

    def test_a_contract_with_targets_remains_hashable(self):
        contract = DecisionContract(
            allowed={"approve", "deny"},
            stability_targets={"deny": 0.01},
        )
        assert isinstance(hash(contract), int)


class TestMinimumCasesIsADeclarationNotACalculation:
    """Nothing in the statistics can infer semantic breadth, so this number
    comes from review and is validated like any other declared field."""

    def test_a_minimum_survives_a_round_trip(self):
        contract = DecisionContract(
            allowed={"approve", "deny"}, minimum_cases={"deny": 3}
        )
        restored = DecisionContract.from_dict(contract.to_dict())
        assert dict(restored.minimum_cases) == {"deny": 3}

    def test_a_contract_without_minimums_omits_the_key(self):
        contract = DecisionContract(allowed={"approve"})
        assert "minimum_cases" not in contract.to_dict()
        assert dict(contract.minimum_cases) == {}

    def test_a_minimum_for_a_decision_that_is_not_required_is_rejected(self):
        with pytest.raises(ValueError, match="not required"):
            DecisionContract(allowed={"approve"}, minimum_cases={"deny": 2})

    def test_a_minimum_below_one_is_rejected(self):
        with pytest.raises(ValueError, match="at least 1"):
            DecisionContract(allowed={"approve"}, minimum_cases={"approve": 0})

    @pytest.mark.parametrize("bad", [2.5, "3", True, None])
    def test_a_non_integer_minimum_is_rejected(self, bad):
        with pytest.raises(TypeError, match="must be an integer"):
            DecisionContract(allowed={"approve"}, minimum_cases={"approve": bad})

    def test_minimums_must_be_a_mapping(self):
        with pytest.raises(TypeError, match="must be a mapping"):
            DecisionContract(allowed={"approve"}, minimum_cases=[("approve", 2)])
