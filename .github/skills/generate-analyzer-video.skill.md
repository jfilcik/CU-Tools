---
name: generate-analyzer-video
description: Creates and tests CU video analyzers with keyframe-grounded string timestamps, official cu local-file execution, and reviewed temporal/detection evaluation.
---

# Skill: Generate Video Analyzer

Use for object/event extraction with temporal grounding. Follow
[Agents.md](../../Agents.md) for API rules,
[Iterate Analyzer Schema](iterate-analyzer-schema.skill.md) for experiment
workflow, and [iteration workspaces](../../docs/iteration-workspaces.md) for
manifests, verified bugs, cost, and STP.

## 1. Freeze a bounded video scope

Select `case\iterations\NNN` and 3–5 representative, authorized local videos.
Start with short clips (for example under two minutes), then evaluate longer
content in a new numbered experiment. Keep customer video and evidence private.
Record hypothesis/baseline, expected/actual defects, video/schema hashes,
independently checked duration, reviewed truth, and evaluator versions.

Preserve raw timestamps under `outputs\raw\`; frame review, timestamp checks,
and post-processing belong under `outputs\evaluation\`. Changes to scope,
schema, normalization, or metric rules require a new number. Obtain explicit
cost approval before service calls and repeated/scale work.

## 2. Design for observable grounding

Video responses can expose transcript, keyframe, and temporal segment details.
Inspect what the selected API/analyzer actually returns; do not infer model
implementation details from output alone. A returned
keyframe timestamp establishes a sampled observation time, **not** the true
first appearance between samples or correctness of the detected object.

Use `prebuilt-video`, `returnDetails: true`, and generated structured fields.
Prefer string timestamps in `hh:mm:ss.ms` (for example `00:00:06.375`) to
avoid requiring the model to convert units. Define events narrowly and
require available keyframe grounding; do not infer arbitrary times.

```json
{
  "description": "Identify supported product appearances at observed keyframe times",
  "baseAnalyzerId": "prebuilt-video",
  "config": { "returnDetails": true },
  "models": { "completion": "gpt-4.1" },
  "fieldSchema": {
    "fields": {
      "DetectedObjects": {
        "type": "array",
        "method": "generate",
        "description": "List distinct products clearly supported by the available video evidence. For each product, use its earliest supported keyframe timestamp; do not guess an appearance between keyframes. Omit detections without sufficient evidence.",
        "items": {
          "type": "object",
          "description": "One supported product appearance and its observed keyframe timestamp.",
          "properties": {
            "ObjectName": {
              "type": "string",
              "method": "generate",
              "description": "Name of the product supported by the video evidence; include a brand only when clearly identifiable."
            },
            "StartTime": {
              "type": "string",
              "method": "generate",
              "description": "Copy the earliest supported keyframe timestamp for this product in hh:mm:ss.ms format, such as 00:00:06.375. Do not interpolate or invent a timestamp."
            }
          }
        }
      }
    }
  }
}
```

This is a starting schema, not a guarantee of timestamp or detection accuracy.
Do not use image filenames as the temporal contract. For segmentation, consult
the documented `contentCategories`/`enableSegment` contract; do not invent
segmentation properties or assume recursive document routing applies to video.

## 3. Validate and execute through official `cu`

Replace placeholders and run from the repository root, using the official CLI
configuration in [README](../../README.md).

```powershell
cu analyzer validate "{iteration_folder}\inputs\schemas\video.json" `
  --api-version 2025-11-01 --spec
python tools\cu-analyzer-validate\cu_analyzer_validator.py `
  "{iteration_folder}\inputs\schemas\video.json" --api-version 2025-11-01
```

After offline checks pass, create a fresh versioned analyzer:

```powershell
cu analyzer create --name video_001 `
  --schema "{iteration_folder}\inputs\schemas\video.json" `
  --api-version 2025-11-01
```

Stop on failure. Only after successful creation and paid-run approval:

```powershell
cu analyze "{short_video_path}" --analyzer video_001 --json `
  --api-version 2025-11-01 --yes --on-existing error `
  --output-dir "{iteration_folder}\outputs\raw\analysis" `
  --report-file "{iteration_folder}\outputs\raw\video-status.json"
python tools\cu-results-export\export.py `
  --input "{iteration_folder}\outputs\raw\analysis" `
  --output "{iteration_folder}\outputs\evaluation\results.csv"
```

Native folder batches and five/ten parallel repeats follow
[Eval CU](eval-cu.skill.md). Apply the same API/profile to all operations.
Cleanup is an explicit `cu analyzer delete video_001` for the owned analyzer
when authorized, not an automatic action.

## 4. Evaluate timestamps and detections separately

Use [the video evaluation prompt](../prompts/evaluate-analyzer-video.prompt.md).
Inspect native `.result.json` contents without assuming a nested envelope.
When available, compare generated timestamps to returned keyframe times
(including `KeyFrameTimesMs` in formats that expose it). Missing keyframe or
duration metadata is unknown, not an empty timeline or zero duration.

Predeclare timestamp parsing, exact-match/near-match tolerances, unit
conversion, and duration bounds. A tolerance such as 500 ms may suit navigation
UX but is not proof of an event's true onset. Separately review frames/source
video to score product/event correctness and missed detections.

| Video scope | Evaluation emphasis |
|---|---|
| Short clips | Establish parser, keyframe alignment, and detection baseline |
| Medium-length content | Check multiple scenes, transitions, and entity retention |
| Long content | Audit omissions, coverage, repeated events, latency, and cost |

Do not extrapolate short-clip scores to longer videos or promise 100% alignment.
Predeclare workload-specific targets (for example zero out-of-bounds times);
report actual counts and denominators. Lower object counts on long videos
may indicate missed coverage and require review—not automatic acceptance.

## 5. Handle limitations without another backend

The verified PyPI CLI accepts local files; it has no URL-input or configurable
analysis-timeout option. Check the selected API's documented file/duration
limits and record compatibility failures. Do not adopt historical upload-size
thresholds as universal service rules or switch to custom service calls.

If a video cannot be processed through the installed official CLI, record the
blocker. An authorized smaller local clip is a new input/scope: preserve the
original, hash the derived clip, record source offsets, and adjust evaluation
without implying full-video coverage. Do not silently resubmit failed calls
or bypass content safety controls.

Optional snapping/clamping is a separately versioned offline transformation,
not a repair to raw evidence. Keep original values, quantify adjustments, and
reject/flag invalid or unsupported timestamps rather than hiding them. Score
raw and transformed output independently; snapping cannot validate an object.

## 6. Close the experiment

Record reviewed correctness, keyframe/duration checks, coverage, failures,
trial counts, metric sources, and holdout/audit limits. CLI reports are status
evidence, not guaranteed per-file usage/timing. Missing values remain unknown;
usage-based pricing is estimated, not measured charges.

Complete cost/basis for every iteration, report the decision, link verified
bugs separately from local defects, and refresh the root index. Temporal
alignment, object counts, fill, and confidence alone do not establish STP.
