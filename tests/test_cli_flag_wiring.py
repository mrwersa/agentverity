"""A flag a command accepts must reach the run it configures.

`--sequential` was declared on the shared parser and read by `run` alone, so
`agentverity snapshot --sequential` parsed, ran, and changed nothing. That is
the fourth instance of one shape in this codebase: a flag accepted and
discarded. The others were `--input-path` defaulting to Promptfoo's convention,
`--layer` and `--provider` on the wrong source, and `--isolation` overridden by
the evidence file.

So this checks the wiring itself rather than one flag: every command whose
parser declares an option that `RunConfig` also carries must pass it through.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from agentverity import cli
from agentverity.cli import _build_parser, main
from agentverity.runner import RunConfig


def _shared_flags() -> list[tuple[str, str]]:
    """(command, RunConfig field) for every option a command shares with it.

    Read from the parser and the dataclass rather than listed here, so a new
    flag or a new command is covered without anyone remembering to add it.
    Inverted flags such as `--no-meter` do not match by name and are checked
    by their own tests.
    """
    fields = {field.name for field in dataclasses.fields(RunConfig)}
    pairs = []
    for action in _build_parser()._subparsers._group_actions:
        for name, parser in action.choices.items():
            for option in parser._actions:
                if not option.option_strings:
                    continue
                field = option.option_strings[0].lstrip("-").replace("-", "_")
                if field in fields:
                    pairs.append((name, field))
    return sorted(set(pairs))


def _commands_declaring(flag: str) -> list[str]:
    """Command names whose parser accepts `flag`, read from the parser."""
    return sorted(
        name
        for action in _build_parser()._subparsers._group_actions
        for name, parser in action.choices.items()
        if any(flag in option.option_strings for option in parser._actions)
    )


def test_the_flag_is_declared_where_it_is_expected():
    """Guards the guard: a typo here would make everything below vacuous."""
    # `check` deliberately does not offer it: it reproduces the sizing the
    # snapshot recorded, down to `k`, so it cannot also size from checkpoints.
    assert _commands_declaring("--sequential") == ["run", "snapshot"]
    assert len(_shared_flags()) >= 20


@pytest.mark.parametrize(("command", "field"), _shared_flags())
def test_a_shared_flag_reaches_the_config_it_names(command, field):
    """Every command that accepts a `RunConfig` option must forward it.

    Checked by source rather than by running each combination, because the
    values differ per flag and the defect is structural: the command builds a
    `RunConfig` and leaves one field out. `check` is exempt for the sizing
    fields it deliberately takes from the snapshot instead, and it does not
    declare those flags, so nothing here reaches that case.
    """
    source = Path(cli.__file__).read_text(encoding="utf-8")
    handler = {
        "run": "_run_command",
        "snapshot": "_snapshot_command",
        "check": "_check_command",
        "assess": "_assess_command",
        "plan": "_plan_command",
        "compare-evidence": "_compare_evidence_command",
    }[command]
    start = source.index(f"def {handler}(")
    body = source[start:]
    end = body.find("\ndef ", 1)
    body = body[:end] if end > 0 else body

    if "RunConfig(" not in body:
        pytest.skip(f"{command} builds no RunConfig")
    assert f"{field}=" in body, (
        f"{command} accepts --{field.replace('_', '-')} and its handler never "
        f"passes {field} to RunConfig"
    )


@pytest.mark.parametrize("command", _commands_declaring("--sequential"))
def test_every_command_accepting_sequential_passes_it_through(
    command, tmp_path, monkeypatch
):
    """Parsed and ignored is the failure this pins, not parsed and refused.

    The source check above catches an omitted field; this one proves the
    value actually arrives, which a stray literal would not.
    """
    inputs = tmp_path / "inputs.txt"
    inputs.write_text(
        "\n".join(
            [f"input_{index}" for index in range(3)]
            + [f"secret_{index}" for index in range(3)]
        ),
        encoding="utf-8",
    )
    seen: list[RunConfig] = []
    real_run = cli.run

    def capturing(*args, **kwargs):
        seen.append(kwargs["config"])
        return real_run(*args, **kwargs)

    monkeypatch.setattr(cli, "run", capturing)

    argv = [
        command,
        "--agent", "examples.toy_agent:deterministic_gate",
        "--inputs", str(inputs),
        "--sequential",
    ]
    if command == "snapshot":
        argv += ["--output", str(tmp_path / "snapshot.json"), "--accept-reference"]
    if command == "check":
        main([
            "snapshot",
            "--agent", "examples.toy_agent:deterministic_gate",
            "--inputs", str(inputs),
            "--output", str(tmp_path / "baseline.json"),
            "--accept-reference",
        ])
        seen.clear()
        argv += ["--snapshot", str(tmp_path / "baseline.json")]

    main(argv)

    assert seen, f"{command} never called run"
    assert all(config.sequential for config in seen), (
        f"{command} accepts --sequential and does not pass it on"
    )


def test_sequential_actually_changes_what_a_snapshot_records(tmp_path, capsys):
    """The wiring above is necessary and not sufficient: prove the effect.

    Six inputs, where the fixed sizing lands on 78 pairs and the checkpoint
    budget is 72, so the two paths are distinguishable. With fifty inputs they
    both land on 100 and this test would pass while asserting nothing.
    """
    import json

    inputs = tmp_path / "inputs.txt"
    inputs.write_text(
        "\n".join(
            [f"input_{index}" for index in range(3)]
            + [f"secret_{index}" for index in range(3)]
        ),
        encoding="utf-8",
    )

    recorded = {}
    for label, extra in (("fixed", []), ("sequential", ["--sequential"])):
        output = tmp_path / f"{label}.json"
        assert main([
            "snapshot",
            "--agent", "examples.toy_agent:deterministic_gate",
            "--inputs", str(inputs),
            "--output", str(output), "--accept-reference", *extra,
        ]) == 0
        recorded[label] = json.loads(output.read_text())["admission_evidence"][
            "meter_pair_trials"
        ]
    capsys.readouterr()

    assert recorded["fixed"] == 78
    assert recorded["sequential"] == 72


def test_check_does_not_offer_a_flag_it_could_not_honour(tmp_path, capsys):
    """A parse error the caller sees at once, not a refusal after loading.

    `check` builds its config from the snapshot, `k` included, and `k` and
    sequential collection size the same run two different ways. Wiring the
    flag through anyway produced a runtime refusal after the agent had been
    imported, which is a worse way to learn the same thing.
    """
    with pytest.raises(SystemExit):
        main(["check", "--agent", "a:b", "--inputs", "x", "--snapshot", "y",
              "--sequential"])

    assert "unrecognized arguments: --sequential" in capsys.readouterr().err


def test_k_and_sequential_are_refused_together():
    """Two rules sizing one run, and the silent winner was the wrong one.

    Sequential collection ignored `k` outright: on six inputs `k=4` asked for
    24 calls and spent 144, and `k=40` asked for 240 and spent the same 144.
    """
    with pytest.raises(ValueError, match="cannot both hold"):
        cli.run(
            lambda text: text,
            ["a", "b"],
            config=RunConfig(k=4, sequential=True),
        )
