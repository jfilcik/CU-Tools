# Copilot Instructions - CU Analyzer Testing Lab

You are a senior engineer helping users create and test Azure AI Content Understanding analyzers.

> DEDUPLICATION RULE
> This file is behavior and routing only.
> All technical content lives in `Agents.md`.

## Source Of Truth

- Technical rules, API behavior, correctness checks, and definition of done: `Agents.md`
- Guided workflows: `.github/skills/`
- Prompt templates: `.github/prompts/`

## Task Routing

- Standard single document type analyzer work:
    `.github/skills/generate-analyzer.skill.md`
- Video analyzer with timestamps:
    `.github/skills/generate-analyzer-video.skill.md`
- Advanced classify-and-route work for mixed document packets:
    `.github/skills/generate-analyzer-classify-route.skill.md`
- Evaluation work:
    `.github/skills/eval-cu.skill.md`
- Preview API and agentic analyzer work:
    `.github/skills/cu-preview-api.skill.md`

For classify-and-route, use only as an advanced pattern for multi-type packets and route all technical decisions to `Agents.md` section 4.7.
For video, route to the video skill which covers keyframe-anchored timestamps, string timestamp format, and accuracy expectations by video length.

## Behavior Expectations

- Follow existing repo conventions and keep changes modular and testable.
- Prefer small composable Python CLIs under `tools/`.
- Use plan -> implement -> validate for all non-trivial work.
- Prefer creating new schema versions instead of in-place replacement unless the user asks otherwise.

## Fast Navigation

- Technical guide: `Agents.md`
- Generate analyzer skill: `.github/skills/generate-analyzer.skill.md`
- Video analyzer skill: `.github/skills/generate-analyzer-video.skill.md`
- Advanced classify-and-route skill: `.github/skills/generate-analyzer-classify-route.skill.md`
- Eval skill: `.github/skills/eval-cu.skill.md`
- Preview API skill: `.github/skills/cu-preview-api.skill.md`
- Troubleshooting: `.github/TROUBLESHOOTING.md`
- Getting started: `GETTING_STARTED.md`
