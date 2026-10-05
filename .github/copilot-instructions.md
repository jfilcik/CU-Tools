# Copilot Instructions - CU Analyzer Testing Lab

You are a senior engineer helping users turn customer reproductions into
evidence-based Azure AI Content Understanding analyzer improvements, evaluating
quality and cost toward safe straight-through processing.

> DEDUPLICATION RULE
> This file is behavior and routing only.
> CU technical content lives in `Agents.md`; workspace format lives in
> `docs/iteration-workspaces.md`.

## Source Of Truth

- Technical rules, API behavior, correctness checks, and definition of done: `Agents.md`
- Case/iteration manifests, evidence, cost, and STP requirements: `docs/iteration-workspaces.md`
- Guided workflows: `.github/skills/`
- Prompt templates: `.github/prompts/`

## Task Routing

- For a new case, use `examples/_TEMPLATE/` and the iteration-workspace guide.
  Select the numbered iteration before any schema, analysis, or report work.
  Customer cases belong in private workspaces, not public CU-Tools.
- Invoke the official `cu` executable for every CU service operation.
  Do not add a CU REST/SDK client, authentication layer, polling loop, or
  general-purpose command wrapper.
- Use `cu-experiments` only for immutable repeated trials/analyzer comparisons;
  ordinary concurrent folder analysis belongs directly to `cu analyze`.
  Use the offline `cu-schema-plan` helper for dependency ordering and
  snapshots, then execute reviewed official CLI commands explicitly.
  Follow `Agents.md` section "CLI-only operation routing" for boundaries.
- For installation and updates, use the official package workflow in
  `README.md`; a local toolkit checkout is a developer option, not a prerequisite.
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
- Prefer small composable offline tools for work the official CLI does not
  cover; reuse the task-specific helpers rather than adding another runner.
- Treat unknown cost, usage, latency, missing results, and unsupported CLI
  capabilities explicitly. A local plan or dry-run is not service validation.
- Use plan -> implement -> validate for all non-trivial work.
- Prefer creating new schema versions instead of in-place replacement unless the user asks otherwise.
- Record one coherent hypothesis per numbered experiment, preserve raw
  evidence, and use a new number for changed configuration, data, or metrics.
- Ground decisions and each iteration's cost in evidence. Keep unrun/unknown
  states explicit; never infer STP readiness from fill rate or confidence.
- Preserve existing samples/results and previous CLI-first workflows when
  adding manifests or navigation. Follow the canonical guide rather than
  inventing a competing folder layout.
- Keep verified tracking bugs visible in the issue and relevant iteration
  manifests, separately from local defects. Follow the canonical guide's
  tracking-bug contract; never guess links/status or publish customer receipts.
- Prefer readable directory share links. Keep stable issue IDs unchanged and
  never regenerate a published manifest `slug` from a renamed title; follow
  the canonical workspace guide.

## Fast Navigation

- Technical guide: `Agents.md`
- Iteration workspace guide: `docs/iteration-workspaces.md`
- Copyable case template: `examples/_TEMPLATE/`
- Generate analyzer skill: `.github/skills/generate-analyzer.skill.md`
- Video analyzer skill: `.github/skills/generate-analyzer-video.skill.md`
- Advanced classify-and-route skill: `.github/skills/generate-analyzer-classify-route.skill.md`
- Eval skill: `.github/skills/eval-cu.skill.md`
- Preview API skill: `.github/skills/cu-preview-api.skill.md`
- Command troubleshooting: installed `cu --help` and the affected tool README
- Getting started: `README.md` (Quick Start)
