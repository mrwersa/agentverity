# Window B findings

Collected 2026-08-23 against the same ten reviewed requests, three models,
146 repeats per request, using the committed collector. Total cost $0.6656
across 4,380 collection attempts over about 14.8 wall-clock minutes. 4,373
attempts became observations; nova dropped seven failed attempts, leaving one
request with 139 observations and 69 usable pairs instead of 73. The drift
criterion was prespecified in
[PRESPECIFICATION.md](PRESPECIFICATION.md) before this window ran.

## Primary outcome: zero call-class changes

No request changed its admit / reject / undecided class between windows, on
any of the three models. `changed_routes` is empty in all three drift reports.

**The stored reports still say `drifted: true` for all three models, and that
is not a contradiction.** The flag fires when anything moved between windows,
including flip counts, wall time, worker count and observed cost. The
prespecified primary outcome is the call class, which did not move. Read
`changed_routes` for the outcome and `drifted` as a change detector. The
distinction matters enough to state twice, because quoting the flag alone would
reverse the finding.

- `gpt4o_mini`: 8 admit, 2 reject — identical to Window A.
- `mistral_small`: 10 admit — identical to Window A.
- `nova`: 1 admit, 6 reject, 3 undecided — identical to Window A.

Per the prespecified interpretation: the frozen baselines held across the
three-week gap.

## Secondary outcomes

- **Flip counts moved inside their windows**: `approve` went 34/73 to 36/73
  for one model and 26/73 to 24/73 for another; nova moved on seven routes.
  Every move stays within its own admission class, consistent with sampling variation around an unchanged route rate. That does
  not exclude provider drift: within-class movement is also what undetected
  drift would look like.
- **Modal actions**: one change in thirty comparisons. Nova's
  "I need some testnet funds" request produced `no_tool_selected` (out of
  contract) in Window A and the correct `request_faucet_funds` in Window B.
  That is a change from out-of-contract to in-contract, and it moved toward
  correct.
- **Isolation**: both windows ran fresh-instance; no isolation change.
- **Errors**: nova recorded 7 collection errors in Window B (none elsewhere).
  Those attempts were dropped rather than recorded, which is why that request
  carries 139 observations and 69 usable pairs. The primary outcome does not
  depend on them: the affected request rejects at 36/69 flips with interval
  [0.406, 0.635], far above the tolerance, so it would reject on any of the
  four missing pairs.

## What this supports

The admitted requests stayed admissible and the rejected requests stayed
rejected across a three-week gap on hosted models whose versions can change
without notice. For the tool-selection layer studied here, frozen baselines
survived their first exposure to operational time.

That is a statement about thirty fixed cells and nothing wider. It is not a
stationarity proof and not an absence of drift: flip counts moved inside their
windows on two models, and nova gained and lost a flip pair. What held is the
class each request was admitted or rejected under. The caveats stand as
stated in [PRESPECIFICATION.md](PRESPECIFICATION.md): two correlated runs
agreeing does not prove independence inside either run, one three-week gap is
one observation, and ten requests bound how far any of this generalises.
