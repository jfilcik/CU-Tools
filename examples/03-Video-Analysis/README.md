# Tutorial 03: Video Analysis — Agent-Based Workflow

Build a video analyzer that detects scenes, objects, and activities with accurate, keyframe-anchored timestamps. This tutorial covers the unique considerations of video analysis in Content Understanding.

## What You'll Learn

- How CU's two-stage pipeline works for video (keyframes + transcript → AI extraction)
- The keyframe-anchored timestamp pattern
- Schema design for temporal fields (scenes, objects with timestamps)
- Classifying video content (sentiment, category)
- Validating timestamps against KeyFrameTimesMs ground truth

## Prerequisites

- Azure AI Foundry with Content Understanding enabled
- Python 3.9+ with dependencies installed (`pip install -r ../../requirements.txt`)
- `.env` configured at repo root (copy from `.env.sample`)
- GitHub Copilot (recommended, but manual steps are provided)

## Sample Video

| File | Type | Duration | What It Contains |
|------|------|----------|------------------|
| `FlightSimulator.mp4` | MP4 | ~37 sec | Flight simulator gameplay footage |

---

## Key Concept: Video Two-Stage Pipeline

Video analysis differs from documents:

```
Stage 1: Content Extraction
  → Extracts audio transcript with timestamps
  → Samples keyframes at specific moments (hh:mm:ss.ms format)
  → Detects camera shot boundaries
  → Output: text descriptions of keyframes + transcript

Stage 2: AI Field Extraction
  → GPT-4.1 analyzes the keyframe descriptions and transcript
  → Uses your field descriptions to extract/generate values
  → ⚠️ The model does NOT see actual video frames — only text about them
```

**Critical implication:** The AI can only reference timestamps that appear in the keyframe list. It cannot observe arbitrary moments in the video.

### The Keyframe Anchoring Rule

When designing timestamp fields:

✅ **DO:** Instruct the model to copy timestamps exactly from the Key Frames list
```json
"startTime": {
  "description": "MUST be copied exactly from a keyframe timestamp. Format: hh:mm:ss.ms"
}
```

❌ **DON'T:** Let the model estimate or interpolate timestamps
```json
"startTime": {
  "description": "When this scene starts"
}
```

---

## Workflow Overview

```
samples/              →  schemas/                →  test_results/     →  reports/
(FlightSimulator.mp4)    (video_analysis_v1.json)   (JSON + keyframes)    (CSV export)
```

> **Note:** Video analysis skips the separate layout extraction step used for documents. The video pipeline handles extraction internally.

---

## Step 1: Review the Schema

Open `schemas/video_analysis_v1.json` to see the video-specific patterns:

**Timestamp fields use `type: "string"`:**
```json
"startTime": {
  "type": "string",
  "method": "generate",
  "description": "...Format: hh:mm:ss.ms. MUST match a keyframe timestamp exactly."
}
```

**Classification fields use `enum`:**
```json
"Sentiment": {
  "type": "string",
  "method": "classify",
  "enum": ["Exciting", "Informational", "Calm", "Dramatic", "Humorous"]
}
```

**Generate vs Extract:** Video fields typically use `method: "generate"` (the model creates structured output from keyframe descriptions) rather than `method: "extract"` (which pulls verbatim text).

---

## Step 2: Validate Schema

```bash
python tools/cu-analyzer-validate/cu_analyzer_validator.py \
  Examples/03-Video-Analysis/schemas/video_analysis_v1.json
```

---

## Step 3: Create Analyzer and Test

**With Copilot:**
```
"Create and test the video analyzer using the schema in 
 Examples/03-Video-Analysis/schemas/video_analysis_v1.json
 with the video in Examples/03-Video-Analysis/samples/"
```

**Manually:**
```bash
python tools/cu-analyzer-run/create_and_test.py \
  --schema Examples/03-Video-Analysis/schemas/video_analysis_v1.json \
  --input Examples/03-Video-Analysis/samples/ \
  --output Examples/03-Video-Analysis/test_results/v1/
```

> **Note:** Video analysis takes longer than document analysis (30-60 seconds typical). The tool polls automatically until complete.

---

## Step 4: Validate Timestamps

After running analysis, check the result JSON files for the `KeyFrameTimesMs` array. This is your ground truth for keyframe positions:

```json
{
  "contents": [{
    "KeyFrameTimesMs": [0, 1500, 3000, 6375, 9750, ...]
  }]
}
```

**Validation levels:**
| Match Quality | Definition | Assessment |
|---------------|------------|------------|
| **Exact** | Generated timestamp matches a KeyFrameTimesMs value | ✅ High confidence |
| **Near** | Within 500ms of a keyframe | ⚠️ Acceptable for navigation |
| **No match** | Timestamp doesn't correspond to any keyframe | ❌ Hallucinated — needs iteration |

---

## Step 5: Export and Evaluate

```bash
python tools/cu-results-export/export.py \
  --input Examples/03-Video-Analysis/test_results/v1/ \
  --output Examples/03-Video-Analysis/test_results/v1/results.csv
```

**What to evaluate for video:**

| Metric | Target | Video-Specific Notes |
|--------|--------|---------------------|
| Timestamp accuracy | >80% exact match | Compare against KeyFrameTimesMs |
| Scene detection | Reasonable boundaries | Camera cuts should trigger new scenes |
| Object detection | Key objects found | Limited to what keyframe captions describe |
| Classification | Correct category | Sentiment and category should match content |

---

## Step 6: Iterate

Common improvements for video schemas:

1. **Tighten timestamp instructions** — Repeat the "MUST copy from Key Frames" rule in every timestamp field
2. **Simplify scene descriptions** — Vague descriptions produce vague results
3. **Adjust object granularity** — Too many objects → noise; too few → missed items
4. **Add duration fields** — Calculate from start of next scene for scene duration

### Large Videos (>20MB)

For videos larger than 20MB, use URL-based analysis with Azure Blob Storage:

```bash
# Upload to blob storage, then use the SAS URL
python tools/cu-analyzer-run/run.py \
  --analyzer-id {your-analyzer-id} \
  --input "https://your-storage.blob.core.windows.net/videos/large_video.mp4?{sas_token}" \
  --output Examples/03-Video-Analysis/test_results/large/
```

---

## API Version Notes

- Use GA API version `2025-11-01`
- `enableSegmentation`, `segmentationMode`, and `segmentationDefinition` are **NOT supported** in the GA API
- For video segmentation (chapters, scenes), use `contentCategories` with `enableSegment: true` — the same classify-and-route pattern used for documents. See the [classify-and-route skill](../../.github/skills/generate-analyzer-classify-route.skill.md).

---

## Folder Structure

```
03-Video-Analysis/
├── README.md                    # This tutorial
├── samples/                     # Source videos
│   └── FlightSimulator.mp4     # Flight simulator gameplay (~37 sec)
├── schemas/                     # Analyzer schemas (versioned)
│   └── video_analysis_v1.json  # Initial video schema with keyframe anchoring
├── test_results/                # Analysis results by run (generated)
└── reports/                     # Summary reports and exports (generated)
```

## Next Steps

- **[Eval Skill](../../.github/skills/eval-cu.skill.md)** — Run systematic evaluations
- **[Video Analyzer Skill](../../.github/skills/generate-analyzer-video.skill.md)** — Advanced video patterns
- **[Classify-and-Route Skill](../../.github/skills/generate-analyzer-classify-route.skill.md)** — Video segmentation via content categories

## Related Resources

- [Agents.md](../../Agents.md) — Technical reference (Section 4.5: Two-Stage Pipeline)
- [Video analyzer skill](../../.github/skills/generate-analyzer-video.skill.md) — Full video workflow reference
- [Analyzer templates](../../analyzer_templates/) — `marketing_video.json`, `content_video.json` examples
