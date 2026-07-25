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

## Concurrent execution

Concurrency is disabled by default. `max_workers` overlaps distinct inputs but
never repeats for one input. Only enable it when the agent and its dependencies
are safe for concurrent calls.
