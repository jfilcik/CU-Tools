---
name: generate-analyzer-video
description: Creates and tests Azure AI Content Understanding video analyzers with accurate keyframe-anchored timestamps. Use when users need to detect objects, scenes, or events in videos with temporal grounding. Covers schema design, timestamp format, keyframe anchoring, and validation patterns for videos of all lengths.
---

# Skill: Generate Video Analyzer

## Quick Start
Use this workflow for video analysis with accurate timestamps.
1. Gather 3-5 representative video samples.
2. Run a single test to understand keyframe structure.
3. Define fields using the keyframe-anchored timestamp pattern.
4. Test on short videos first, then scale to longer content.
5. Validate timestamps against KeyFrameTimesMs ground truth.

Core commands:
```bash
python tools/cu-analyzer-run/create_and_test.py --schema {project_folder}/schemas/{name}_v1.json --input {sample_folder} --output {project_folder}/test_results/v1
python tools/cu-results-export/export.py --input {project_folder}/test_results/v1 --output {project_folder}/test_results/v1/results.csv
```

## Video-Specific Concepts

### Two-Stage Pipeline for Video
CU processes video in two stages:
1. **Stage 1**: Extracts audio transcript, keyframes at specific timestamps, and camera shot boundaries
2. **Stage 2**: GPT-4.1 analyzes the extracted text + keyframe descriptions to generate field values

**What the LLM sees** (in Stage 2):
- Audio transcript with timestamps
- A "Key Frames" section listing keyframe timestamps in `hh:mm:ss.ms` format (e.g., `00:00:06.375`)
- Camera shot boundaries
- It does **NOT** see the actual video frames — only text descriptions of them

This means:
- Timestamps MUST reference the Key Frames list — the LLM cannot observe arbitrary moments
- Object detection is limited to what's described in keyframe captions
- The `keyFrame.XXXX.jpg` filename format is API-level output only; the prompt uses `hh:mm:ss.ms`

### KeyFrameTimesMs Ground Truth
Every video result includes `contents[].KeyFrameTimesMs` — an array of millisecond timestamps for all pipeline-extracted keyframes. Use this to validate generated timestamps:
- **Exact match**: Generated timestamp matches a value in KeyFrameTimesMs → high confidence
- **Near match**: Within 500ms of a keyframe → acceptable for navigation UX
- **No match / exceeds duration**: Hallucinated timestamp → needs post-processing

### API Version Requirements
- Use GA API version `2025-11-01`
- `enableSegmentation`, `segmentationMode`, and `segmentationDefinition` are **NOT supported** in the GA API
- For video segmentation, use `contentCategories` with `enableSegment: true` (see generate-analyzer-classify-route.skill.md)

## Workflow

### 1) Gather Inputs
Checklist:
- Collect 3-5 video files covering different content types and lengths
- Start with short videos (<2 min) for initial schema development
- Confirm environment variables: AZURE_AI_ENDPOINT, AZURE_AI_API_KEY
- For videos >20MB, use URL-based analysis via Azure Blob Storage (see Large Video section)

### 2) Design Schema — Timestamp Fields

#### ✅ Recommended Pattern: String Timestamps in hh:mm:ss.ms

Use `type: "string"` for timestamp fields with the `hh:mm:ss.ms` format. This matches the format used in the internal prompt's Key Frames section, giving the LLM the best chance of copying timestamps exactly.

```json
{
  "description": "Video object detection — keyframe-anchored timestamps",
  "baseAnalyzerId": "prebuilt-video",
  "config": {
    "returnDetails": true,
    "locales": ["en-US"],
    "disableContentFiltering": true
  },
  "fieldSchema": {
    "fields": {
      "detectedObjects": {
        "type": "array",
        "method": "generate",
        "description": "Identify all distinct physical objects, products, brand logos, and notable items visible in the video. For each object, report its name and the EXACT timestamp (in hh:mm:ss.ms) where the object first appears. CRITICAL: The startTime value MUST be copied exactly from one of the keyframe timestamps. DO NOT interpolate, estimate, or generate timestamps that are not in the Key Frames list. If an object does not clearly appear in any keyframe, use the nearest keyframe where it is partially visible.",
        "items": {
          "type": "object",
          "properties": {
            "objectName": {
              "type": "string",
              "method": "generate",
              "description": "Descriptive name of the object. Be specific, include brand names when visible."
            },
            "startTime": {
              "type": "string",
              "method": "generate",
              "description": "The EXACT keyframe timestamp in hh:mm:ss.ms where this object first appears. This value MUST match one of the timestamps from the Key Frames section. For example: 00:00:00.750, 00:00:01.500, 00:00:06.375, etc. Do NOT use any value that is not listed as a keyframe timestamp."
            }
          }
        }
      }
    }
  },
  "models": { "completion": "gpt-4.1" }
}
```

#### Key Design Rules

1. **Timestamp type MUST be `string`** — Use `hh:mm:ss.ms` format (e.g., `"00:00:06.375"`), not integer milliseconds. The Key Frames section in the internal prompt uses this format, so string matching yields higher keyframe accuracy.

2. **Keyframe anchoring is CRITICAL** — Field descriptions must explicitly instruct the LLM to copy timestamps from the Key Frames list. Without this, the LLM will hallucinate timestamps that exceed the video duration.

3. **Be specific about what to detect** — Instead of "detect all objects", specify the categories relevant to your use case: "physical objects, products, brand logos, and notable items". This improves precision.

4. **Use `method: "generate"`** — Video object detection with timestamps requires `generate`, not `extract`. The LLM must synthesize object-timestamp pairs from the keyframe descriptions.

5. **Always enable `returnDetails: true`** — This returns KeyFrameTimesMs, cameraShotTimesMs, and other metadata needed for timestamp validation.

#### ❌ Patterns to Avoid

- **Integer millisecond timestamps** (`type: "integer"`, `startTimeMs`): The LLM must convert from hh:mm:ss.ms to ms, introducing conversion errors and hallucination
- **Referencing `keyFrame.XXXX.jpg` filenames**: This format is API output only; the internal prompt uses `hh:mm:ss.ms`
- **Vague descriptions**: "Get timestamps for objects" → Be explicit about keyframe anchoring
- **enableSegmentation config**: Not supported in GA API 2025-11-01

### 3) Validate and Test

```bash
# Validate schema
python tools/cu-analyzer-validate/cu_analyzer_validator.py {project_folder}/schemas/{name}_v1.json

# Create analyzer and test on short videos first
python tools/cu-analyzer-run/create_and_test.py \
  --schema {project_folder}/schemas/{name}_v1.json \
  --input {short_videos_folder} \
  --output {project_folder}/test_results/v1
```

### 4) Validate Timestamps

After testing, validate timestamp accuracy against KeyFrameTimesMs:

```python
import json, re

def parse_timestamp_to_ms(ts_str):
    """Parse hh:mm:ss.ms to milliseconds."""
    m = re.match(r'^(\d+):(\d+):(\d+)[.,](\d+)$', str(ts_str))
    if m:
        h, mn, s, frac = m.groups()
        ms = int(frac.ljust(3, '0')[:3])
        return int(h)*3600000 + int(mn)*60000 + int(s)*1000 + ms
    return None

# Load result
with open("result.json") as f:
    result = json.load(f)

contents = result["result"]["contents"]
for content in contents:
    kf_times = set(content.get("KeyFrameTimesMs", []))
    duration_ms = content.get("endTimeMs", 0)

    objects = content["fields"]["detectedObjects"]["valueArray"]
    for obj in objects:
        vo = obj["valueObject"]
        name = vo["objectName"]["valueString"]
        ts_str = vo["startTime"]["valueString"]
        ts_ms = parse_timestamp_to_ms(ts_str)

        in_keyframes = ts_ms in kf_times
        exceeds = ts_ms > duration_ms if ts_ms else False
        print(f"  {name}: {ts_str} → {ts_ms}ms | KF match: {in_keyframes} | Exceeds: {exceeds}")
```

**Quality metrics to track:**
- **KF Match %**: Percentage of timestamps that exactly match a KeyFrameTimesMs value (target: >90% for short videos)
- **Exceeds %**: Timestamps that exceed video duration (target: 0%)
- **Avg KF Delta**: Average distance from nearest keyframe in ms (target: <500ms)

### 5) Scale to Longer Videos

#### Expected accuracy by video length

With the recommended V1c pattern (string timestamps in `hh:mm:ss.ms`):

| Video Length | Expected KF Match | Expected Exceeds | Notes |
|-------------|-------------------|-----------------|-------|
| <1 min | 100% | 0% | Perfect — tested on 30-44s ads |
| 1-2 min | 100% | 0% | Perfect — tested on 93s video |
| 5-15 min | 100% | 0% | Perfect — tested on 14.9m Disney broadcast |
| 15-60 min | 100% | 0% | Perfect — tested on 57.9m Disney broadcast |

> **Note**: Object count naturally decreases on very long videos (24 objects on 58-min vs 57 on 15-min).
> The LLM has limited context for very long keyframe lists, but all generated timestamps are accurate.

#### Large Video Upload (>20MB)

For videos larger than ~20MB, use URL-based analysis to avoid upload timeouts:

```python
# Upload to Azure Blob Storage first, then analyze via URL
from content_understanding_client import AzureContentUnderstandingClient

client = AzureContentUnderstandingClient(endpoint, api_version="2025-11-01", subscription_key=key)
resp = client.begin_analyze_url(analyzer_id, blob_url_with_sas)
result = client.poll_result(resp, timeout_seconds=2400)
```

- Local binary upload: practical limit ~20MB (connection resets on larger files)
- URL-based: tested successfully on videos up to 446MB / 58 minutes
- Set timeout proportional to video length: ~30-40x the video duration in seconds

### 6) Post-Processing Recommendations

For production use, always post-process timestamps:

```python
def snap_to_keyframe(ts_ms, keyframe_times_ms, duration_ms):
    """Clamp to duration and snap to nearest keyframe."""
    if ts_ms is None:
        return None
    # Clamp to valid range
    ts_ms = max(0, min(ts_ms, duration_ms))
    # Snap to nearest keyframe
    if keyframe_times_ms:
        nearest = min(keyframe_times_ms, key=lambda k: abs(k - ts_ms))
        return nearest
    return ts_ms
```

This handles:
- Timestamps that exceed video duration (clamp)
- Timestamps between keyframes (snap to nearest)
- Edge cases on very long videos where LLM approximates

### 7) Visual Validation (Optional)

Generate an HTML report with actual video frames at each detected timestamp:

```bash
python Issues/LuciHub/validate_frames.py \
  --results {project_folder}/test_results/v1 \
  --output {project_folder}/test_results/v1/validation.html
```

This extracts the actual frame at each timestamp and displays it with the object label, making it easy to manually verify detection accuracy.

## Output Structure
```
Issues/{project}/
├── samples/              # Video files
├── schemas/
│   └── {name}_v1.json    # Video analyzer schema
├── test_results/
│   └── v1/
│       ├── *.json         # Raw CU results per video
│       ├── results.csv    # Exported results
│       └── validation.html # Visual frame validation
└── reports/
```

## Success Criteria
- Schema validates cleanly
- Short videos (<2 min): 100% keyframe match, 0% exceeds
- Medium videos (2-5 min): 100% keyframe match, 0% exceeds
- Long videos (>5 min): 100% keyframe match, 0% exceeds (object count may be lower)
- Results exported and validated visually

## Common Issues

### Timestamps exceed video duration
**Cause**: LLM hallucinates timestamps beyond the video length.
**Fix**: Ensure field descriptions include explicit keyframe anchoring instructions. Use string type (`hh:mm:ss.ms`) not integer. Always post-process with snap-to-keyframe.

### Content safety filter rejections
**Cause**: Azure OpenAI content filters flag legitimate video content.
**Fix**: Add `"disableContentFiltering": true` to the config section. Note: this may not be available in all deployments.

### Low object count on long videos
**Cause**: LLM has limited context window for very long transcripts/keyframe lists.
**Fix**: Expected behavior. For >15 min videos, consider pre-splitting into segments, or accept lower detection density.

### Timeout on large videos
**Cause**: Large file upload or long processing time.
**Fix**: Use URL-based analysis (`begin_analyze_url`) for videos >20MB. Set timeout to 30-40x video duration.

### `enableSegmentation` not supported
**Cause**: This config option is preview-only, not in GA API 2025-11-01.
**Fix**: Use `contentCategories` with `enableSegment: true` for video segmentation (same pattern as document classify-and-route). See `generate-analyzer-classify-route.skill.md`.

## Related Resources
- Standard document analyzer: `generate-analyzer.skill.md`
- Classify-and-route (segmentation): `generate-analyzer-classify-route.skill.md`
- Technical rules: `Agents.md` sections 4.5 (two-stage pipeline) and 4.6 (schema design)
- LuciHub investigation: `Issues/LuciHub/README.md` (full test results and analysis)
- Reference schema: `Issues/LuciHub/schemas/v1c_string_timestamps.json`
- Visual validation tool: `Issues/LuciHub/validate_frames.py`

## Related Prompts
- Video-specific eval: `.github/prompts/evaluate-analyzer-video.prompt.md`
- Core eval workflow: `.github/prompts/evaluate-analyzer.prompt.md`
- Classify-and-route schema: `.github/prompts/classify-and-route-schema.prompt.md`
- Write field descriptions: `.github/prompts/write_schema_fields.prompt.md`
