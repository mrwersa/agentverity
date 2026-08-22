# Security and data handling

## Reporting vulnerabilities

Please report a suspected vulnerability privately through
[GitHub's security advisory form](https://github.com/mrwersa/agentverity/security/advisories/new).
Do not open a public issue for an unpatched vulnerability.

## Probe and output data

AgentVerity machine reports, progress events, and snapshots identify probe
inputs by SHA-256 fingerprint rather than storing the raw text.
Fingerprints are identifiers, not anonymisation. An attacker can test guesses
against a fingerprint when probe text comes from a small or predictable set.

Snapshots retain the approved observation value because it is the reference
being checked. A snapshot over the `text` layer may therefore contain model
output with sensitive content. Recorded exception messages may also echo
provider request data. Store these artefacts under the same controls as test
fixtures and model logs.

The optional OpenTelemetry bridge emits aggregate `agentverity.*` attributes.
It excludes raw prompts, outputs, fingerprints, majority-verdict values,
relation names, and exception messages. Exporters, collectors, and monitoring
backends remain outside AgentVerity's control. Review their retention and
access policy before enabling the bridge.

Decision-suite JSON files are different. They are source test datasets and
contain each raw input plus its intended decision. Treat them like test
fixtures, not privacy-minimised reports. The generated JSON, JUnit, snapshot,
and OpenTelemetry outputs do not copy those raw inputs.

Imported evidence also retains raw inputs and observations. Its `provenance`
mapping is caller supplied and is not filtered. JSON, JUnit, and terminal
diagnostics can echo observation values on finding paths, while JSON and
terminal output retain recorded exception messages. The executable
[security and data-retention audit](docs/security-data-audit.md) maps each
surface and its caveats; “excluded” never means a provider, adapter, exporter,
or caller-controlled field cannot log the same value elsewhere.

## Concurrent execution

Concurrency is disabled by default. `max_workers` overlaps distinct inputs but
never repeats for one input. Only enable it when the agent and its dependencies
are safe for concurrent calls.
