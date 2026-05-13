---
status: ✅ IMPLEMENTED
version: 1.0.0
last_updated: 2026-04-18
---

# Prompt: Evaluate Video Analyzer

Video-specific evaluation overlay for Content Understanding video analyzers. Use alongside the core `evaluate-analyzer.prompt.md` for video-specific metrics and validation.

> **Core eval workflow**: See `evaluate-analyzer.prompt.md` for scale/stability eval patterns, KPIs, and report template. This prompt adds video-specific guidance.

## Video-Specific Eval Considerations

### Timestamp Validation (Critical for Video)

Every video result includes `contents[].KeyFrameTimesMs` — validate generated timestamps against this ground truth:

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

# Load result and validate
with open("result.json") as f:
    result = json.load(f)

for content in result["result"]["contents"]:
    kf_times = set(content.get("KeyFrameTimesMs", []))
    duration_ms = content.get("endTimeMs", 0)

    for field_name, field_val in content.get("fields", {}).items():
        # Check arrays of objects with timestamp fields
        if field_val.get("type") == "array":
            for item in field_val.get("valueArray", []):
                vo = item.get("valueObject", {})
                for k, v in vo.items():
                    ts_str = v.get("valueString", "")
                    ts_ms = parse_timestamp_to_ms(ts_str)
                    if ts_ms is not None:
                        in_kf = ts_ms in kf_times
                        exceeds = ts_ms > duration_ms
                        if not in_kf or exceeds:
                            print(f"  ISSUE: {k}={ts_str} KF={in_kf} Exceeds={exceeds}")
```

### Video-Specific KPIs

| Metric | Description | Target |
|--------|-------------|--------|
| KF Match % | Timestamps matching a KeyFrameTimesMs value exactly | >90% (short), >85% (long) |
| Exceeds % | Timestamps beyond video duration | 0% |
| Avg KF Delta | Average distance from nearest keyframe (ms) | <500ms |
| Object Count | Number of detected items per video | Use case dependent |

### Expected Accuracy by Video Length

| Video Length | Expected KF Match | Expected Exceeds | Notes |
|-------------|-------------------|-----------------|-------|
| <1 min | 100% | 0% | Best accuracy range |
| 1-5 min | 100% | 0% | Reliable |
| 5-60 min | 100% | 0% | Tested on broadcasts up to 58 min |
| >60 min | 95%+ | <1% | May need increased timeout |

### Video Classification Limits

**Videos support only 1 level of classification** (contentCategories). Unlike documents which support 5-6 levels of recursive classify-and-route, video classifiers:
- Can segment a video into categories (e.g., news stories, ad breaks)
- Can route each segment to one inner analyzer for field extraction
- Cannot nest classifiers within classifiers for video content

This is because video segmentation operates on temporal boundaries (keyframes, audio transitions) which don't have the same structural nesting that document pages do.

### Video-Specific Analysis Checklist

For scale evals:
- [ ] All timestamps fall within video duration
- [ ] Timestamps match keyframes (not interpolated)
- [ ] Object detection is consistent with keyframe content
- [ ] Segmentation boundaries are at natural breaks (topic changes, transitions)

For stability evals:
- [ ] Same objects detected across iterations
- [ ] Timestamp values are deterministic (same keyframe selected)
- [ ] Object count is stable (±10% across iterations)

### Post-Processing Recommendations

Always snap timestamps to nearest keyframe in production:

```python
def snap_to_keyframe(ts_ms, keyframe_times_ms, duration_ms):
    """Clamp to duration and snap to nearest keyframe."""
    if ts_ms is None:
        return None
    ts_ms = max(0, min(ts_ms, duration_ms))
    if keyframe_times_ms:
        return min(keyframe_times_ms, key=lambda k: abs(k - ts_ms))
    return ts_ms
```

### Large Video Considerations

- Local upload limit: ~20MB (use URL-based analysis for larger files)
- Set timeout proportional to video length: ~30-40× video duration in seconds
- CU API hard limit: 200MB file size

## See Also

- Core eval workflow: `.github/prompts/evaluate-analyzer.prompt.md`
- Video analyzer creation: `.github/skills/generate-analyzer-video.skill.md`
- Write field descriptions: `.github/prompts/write_schema_fields.prompt.md`
