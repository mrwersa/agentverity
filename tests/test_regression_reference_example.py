"""The onboarding workflow must distinguish repeatability from a match."""

from pathlib import Path

from examples import regression_reference as example


def test_fresh_qualified_evidence_detects_changed_reference(monkeypatch, capsys):
    original_run = example.run
    collections = []

    def counted_run(agent, *args, **kwargs):
        calls = 0

        def counted_agent(text):
            nonlocal calls
            calls += 1
            return agent(text)

        result = original_run(counted_agent, *args, **kwargs)
        collections.append((calls, result))
        return result

    monkeypatch.setattr(example, "run", counted_run)
    example.main()

    assert len(collections) == 3
    for calls, result in collections:
        assert calls >= len(example.INPUTS) * result.config.k
        assert result.meter.call == "verdict-deterministic"
    assert collections[0][1].observed_keys == collections[1][1].observed_keys
    assert collections[0][1].observed_keys != collections[2][1].observed_keys

    output = capsys.readouterr().out
    assert "Reference: ADMITTED (2 reviewed decisions)" in output
    assert "Unchanged router: MATCH (0 changed decisions)" in output
    assert "Changed router: CHANGED (2 changed decisions)" in output
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text()
    for line in output.splitlines():
        assert line in readme
