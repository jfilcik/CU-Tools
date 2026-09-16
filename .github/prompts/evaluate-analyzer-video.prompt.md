# Prompt: Evaluate Video Analyzer

Apply this overlay to [Evaluate Analyzer](evaluate-analyzer.prompt.md).
Temporal alignment and object/event correctness are separate evaluations.

## Bind the experiment

Use [iteration workspaces](../../docs/iteration-workspaces.md) and the selected
`case\iterations\NNN`. Keep customer videos private. Freeze/hash videos and
schemas; version reviewed truth, evaluator, duration source, timestamp parsing,
and post-processing rules. Record hypothesis/baseline, expected/actual defects,
verified bugs, held-out scope, and explicit cost approval.

Read original native `.result.json` files under `outputs\raw\`. Do not assume
a nested result envelope or guaranteed keyframe metadata. Write metrics,
frame review, and transformed derivatives under `outputs\evaluation\`; never
replace raw timestamps. Changed scope or scoring/transformation rules require
a new numbered experiment.

## Timestamp checks

1. Inspect the actual contents and available keyframe times, transcript, and
   segment boundaries. Some saved formats expose `KeyFrameTimesMs`; do not
   assume that field exists in every response.
2. Parse the declared `hh:mm:ss.ms` format deterministically (for example
   `00:00:06.375`), validating minutes/seconds, fractional precision, units,
   and nonnegative values. Invalid or missing values are failures/unknowns,
   not silently discarded or converted to zero.
3. Compare against returned keyframe times **when present** and independently
   checked source duration. Distinguish clip-relative, segment-relative, and
   full-video time; apply only documented, versioned offsets.
4. Report exact matches, near matches under a predeclared tolerance, invalid
   times, out-of-bounds values, and nearest-keyframe distance. Missing
   keyframes/duration means that check is unknown, not passed.
5. Review source frames/video independently for whether the detected object
   or event is actually present. A matching keyframe is not ground truth for
   the detection or an unsampled true first appearance.

## Metrics

| Metric | Definition and denominator |
|---|---|
| Parse validity | Valid timestamps / all expected generated timestamp values |
| Exact keyframe match | Exact matches / timestamps with keyframe evidence; also report missing evidence |
| Out-of-bounds | Values outside verified time bounds / timestamps with valid time and bounds |
| Keyframe distance | Distance in milliseconds over comparable timestamps; report excluded values |
| Detection correctness/coverage | Reviewed supported detections and missed expected objects/events |
| Temporal stability | Selected times, object membership, and count drift across planned trials |

Set targets before the run. Zero out-of-bounds values or a 500 ms navigation
tolerance can be useful goals, not universal measured guarantees. Compare
short, medium, and long videos separately. Longer scope can expose omissions,
coverage loss, or increased cost; do not extrapolate short-video accuracy or
excuse lower counts without reviewing expected content.

For segmentation, verify boundaries and per-segment category/extraction
correctness. Consult [Agents.md](../../Agents.md) and the selected API contract;
do not assume document routing depth applies to video.

## Execution and file limitations

Use the official local-file commands in
[Generate Video Analyzer](../skills/generate-analyzer-video.skill.md).
Ordinary folder analysis uses native CLI concurrency; repeated or multi-analyzer
trials use the cost-gated helper in [Eval CU](../skills/eval-cu.skill.md).

The verified CLI has no URL-input or configurable analysis-timeout option.
Check current documented file/duration limits; do not prescribe a universal
historical upload cutoff or a custom service-call fallback. If needed,
prepare authorized smaller local clips as new immutable inputs with hashes,
source offsets, changed scope, and fresh cost approval. Record blockers and
uncertain completion before any resubmission.

## Optional post-processing

Snapping/clamping is an explicitly versioned offline transformation only.
Preserve raw values, record adjustment magnitudes and unsupported timestamps,
and score raw versus transformed results separately. Invalid timestamps
should be flagged/rejected for review rather than silently made plausible.
When keyframes or duration are missing, do not pretend snapping was verified.
Post-processing cannot establish detection correctness.

## Required outcome

Complete report/manifest and root navigation with timestamp counts/sources,
reviewed detections, coverage, failures/trials, raw/transformed comparisons,
holdout/audit limitations, cost status/basis, and accept/reject/inconclusive
decision. CLI status reports are not guaranteed usage/latency records; absent
measurements remain unknown/null. Usage-based pricing is estimated.

Keyframe alignment, stable counts, fill, and confidence alone do not prove
case-level correctness or STP.
