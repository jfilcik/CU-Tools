# Tutorial 03: Video analysis

Create a video analyzer with grounded scene/object timestamps and evaluate
its outputs against the source video. Use the official CLI for all CU service
operations.

## Prerequisites and sample

Follow the [root Quick Start](../../README.md#quick-start): Python 3.10+,
official CLI profiles, your authorized CU resource/model mappings, and local
reporting dependencies. No repository `.env` is loaded by `cu`.
Run commands from the repository root.

The sample `samples/FlightSimulator.mp4` is approximately 37 seconds of flight
simulator footage. Review data permissions and analysis cost before uploading
any video. For a real case, select a numbered iteration using the
[workspace guide](../../docs/iteration-workspaces.md); keep source/schema
snapshots, raw output, evaluation, and reports together.

## Timestamp design

Temporal evidence is limited by the sampled frames and transcript available
to the analyzer. Instruct timestamp fields to copy available frame timestamps
rather than interpolate arbitrary moments. Use strings, not floating-point
numbers:

```json
{
  "startTime": {
    "type": "string",
    "method": "generate",
    "description": "Copy an available keyframe timestamp exactly for the beginning of this event. Format: hh:mm:ss.mmm. Do not estimate an unsampled time."
  }
}
```

Review `schemas/video_analysis_v1.json` for scene/object descriptions and
classification fields. Do not claim that a generated time is source-grounded
just because it has the right format. Frame alignment and whether the event
actually occurs are separate checks.

## Validate, create, and analyze

```powershell
$case = ".\examples\03-Video-Analysis"
cu analyzer validate "$case\schemas\video_analysis_v1.json" --api-version 2025-11-01
python tools\cu-analyzer-validate\cu_analyzer_validator.py "$case\schemas\video_analysis_v1.json"

cu analyzer create --name tutorial_video_v1 --schema "$case\schemas\video_analysis_v1.json" --api-version 2025-11-01

# Inspect discovery locally first.
cu analyze "$case\samples\FlightSimulator.mp4" --analyzer tutorial_video_v1 `
  --json --output-dir .\video-tutorial\results --dry-run

# Billable: execute only after scope/cost approval.
cu analyze "$case\samples\FlightSimulator.mp4" --analyzer tutorial_video_v1 `
  --json --output-dir .\video-tutorial\results `
  --report-file .\video-tutorial\status.json --api-version 2025-11-01 --on-existing error
```

Use a new versioned analyzer ID/output path if one exists already. The CLI
handles request submission and polling. Video latency varies; the verified
CLI has no `--timeout` flag. Preserve partial evidence before considering a
paid retry, and only delete explicitly owned analyzers when cleanup is intended.

## Evaluate

```powershell
python tools\cu-results-export\export.py `
  --input .\video-tutorial\results --output .\video-tutorial\results.csv
```

Where saved results expose frame timestamps, compare generated timestamps to
that inventory. Do not assume a `KeyFrameTimesMs` array is always present or
fabricate one from generated fields. If frame evidence is absent, record the
limitation and review timestamps directly against the source video.

Measure exact alignment separately from a declared navigation tolerance,
scene/event correctness, object coverage, and classification accuracy.
For example, a 500 ms navigation tolerance is an application policy, not proof
of exact grounding. Include failed/missing results in the denominator.

Record numeric cost/timing only when available with a stated basis. CLI console
usage/time output is not a guaranteed per-document JSON metric. Missing cost
is unknown; good timestamp formatting or high confidence is not STP readiness.

## Iterate

Tighten timestamp/scene descriptions, adjust object granularity, and save a
new schema/analyzer version. Use ordinary CLI batches for multiple videos and
[cu-experiments](../../tools/cu-experiments/README.md) for repeated trials or
analyzer comparisons. Keep the global concurrency and cost budget explicit.

The verified public CLI accepts local files; do not copy obsolete URL/SAS
upload commands or assume a fixed 20 MB cutoff. Check current CLI/service
support for your input and record any unsupported capability rather than
silently switching execution backends. Never put signed URLs in reports.

For segmentation, use supported `contentCategories`/`enableSegment` patterns
appropriate to your API/schema; do not add obsolete `enableSegmentation`,
`segmentationMode`, or `segmentationDefinition` flags. See the
[video skill](../../.github/skills/generate-analyzer-video.skill.md) and
[classify-and-route workflow](../../.github/skills/generate-analyzer-classify-route.skill.md).
