"""Reports and developer handoff artifacts (Phase 8).

Generates:
- Migration summary report (Markdown) with common issues + sorted analyzer table
- Per-analyzer warning report (only for unique/analyzer-specific findings)
- App integration checklist
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from cu_migrate.models import (
    FindingSeverity,
    MigrationResult,
    MigrationRun,
    ValidationStatus,
)

# Severity sort order: highest severity first
_SEVERITY_ORDER = {
    FindingSeverity.NOT_SUPPORTED: 0,
    FindingSeverity.NEEDS_REVIEW: 1,
    FindingSeverity.AUTO_FIXED: 2,
}

_SEVERITY_LABEL = {
    FindingSeverity.AUTO_FIXED: "🟢 Auto-fixed",
    FindingSeverity.NEEDS_REVIEW: "🟡 Review",
    FindingSeverity.NOT_SUPPORTED: "🔴 Not supported",
}

_STATUS_ICON = {
    ValidationStatus.FAIL: "❌",
    ValidationStatus.WARN: "⚠️",
    ValidationStatus.PASS: "✅",
}

_STATUS_ORDER = {
    ValidationStatus.FAIL: 0,
    ValidationStatus.WARN: 1,
    ValidationStatus.PASS: 2,
}


def _finding_key(f) -> str:
    """Unique key for a finding (ignoring analyzer_id) to detect common issues."""
    return f"{f.severity.value}|{f.category}|{f.message}"


def _identify_common_findings(run: MigrationRun) -> list[dict]:
    """Find findings that appear across the majority of analyzers.

    A finding is "common" if its message appears in more than half of all results.
    Returns a list of dicts with severity, category, message, recommended_action, count.
    """
    total = len(run.results)
    if total == 0:
        return []

    # Count how many analyzers each unique finding appears in
    finding_counts: Counter[str] = Counter()
    finding_examples: dict[str, MigrationResult] = {}

    for result in run.results:
        seen_keys: set[str] = set()
        for f in result.findings:
            key = _finding_key(f)
            if key not in seen_keys:
                finding_counts[key] += 1
                seen_keys.add(key)
                if key not in finding_examples:
                    finding_examples[key] = f

    threshold = max(total * 0.5, 2) if total > 2 else total
    common = []
    for key, count in finding_counts.most_common():
        if count >= threshold:
            f = finding_examples[key]
            common.append({
                "severity": f.severity,
                "category": f.category,
                "message": f.message,
                "recommended_action": f.recommended_action,
                "count": count,
            })
    # Sort by severity
    common.sort(key=lambda c: _SEVERITY_ORDER.get(c["severity"], 99))
    return common


def _get_unique_findings(result: MigrationResult, common_keys: set[str]) -> list:
    """Return findings for this analyzer that are NOT in the common set."""
    return [f for f in result.findings if _finding_key(f) not in common_keys]


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(run: MigrationRun) -> str:
    """Generate the full Markdown migration report."""
    lines: list[str] = []

    # Header
    lines.extend([
        "# CU Migration Report",
        "",
        f"**Run ID:** {run.run_id}  ",
        f"**Mode:** {run.mode.value}  ",
        f"**Scope:** {run.scope}  ",
        f"**Timestamp:** {run.timestamp.isoformat()}  ",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Analyzers scanned | {len(run.results)} |",
        f"| ✅ Passed | {run.success_count} |",
        f"| ⚠️ Warnings | {run.warning_count} |",
        f"| ❌ Failed | {run.failure_count} |",
        "",
    ])

    # Common issues section
    common = _identify_common_findings(run)
    common_keys = {
        f"{c['severity'].value}|{c['category']}|{c['message']}" for c in common
    }

    if common:
        lines.extend([
            "## Common Issues (applies to all or most analyzers)",
            "",
            "The following issues were detected across the majority of analyzers "
            "and do not need to be reviewed individually.",
            "",
            "| Severity | Category | Message | Action | Analyzers |",
            "|----------|----------|---------|--------|-----------|",
        ])
        for c in common:
            sev = _SEVERITY_LABEL.get(c["severity"], str(c["severity"]))
            action = c["recommended_action"] or "—"
            lines.append(
                f"| {sev} | {c['category']} | {c['message']} | {action} | {c['count']}/{len(run.results)} |"
            )
        lines.append("")

    # Sorted analyzer table
    sorted_results = sorted(
        run.results,
        key=lambda r: (
            _STATUS_ORDER.get(r.validation_status, 99),
            # Secondary sort: number of unique findings (more = higher)
            -len(_get_unique_findings(r, common_keys)),
            r.source.analyzer_id,
        ),
    )

    lines.extend([
        "## Analyzer Overview",
        "",
        "| Status | Analyzer ID | Proposed GA ID | Base Analyzer | Knowledge Sources | Unique Issues |",
        "|--------|------------|----------------|---------------|-------------------|---------------|",
    ])
    for result in sorted_results:
        icon = _STATUS_ICON.get(result.validation_status, "❓")
        src = result.source
        prop = result.proposed
        unique = _get_unique_findings(result, common_keys)
        unique_count = len(unique)
        ga_id = prop.analyzer_id if prop else "—"
        base = prop.base_analyzer_id if prop else "—"
        ks = str(len(prop.knowledge_sources)) if prop else "0"
        lines.append(
            f"| {icon} | {src.analyzer_id} | {ga_id} | {base} | {ks} | {unique_count} |"
        )
    lines.append("")

    # Per-analyzer details — ONLY for analyzers with unique findings
    analyzers_with_unique = [
        (r, _get_unique_findings(r, common_keys)) for r in sorted_results
        if _get_unique_findings(r, common_keys)
    ]

    if analyzers_with_unique:
        lines.extend([
            "## Analyzer-Specific Issues",
            "",
            "Only analyzers with issues beyond the common set are listed here.",
            "",
        ])
        for result, unique in analyzers_with_unique:
            icon = _STATUS_ICON.get(result.validation_status, "❓")
            lines.extend([
                f"### {icon} {result.source.analyzer_id}",
                "",
            ])
            if result.proposed:
                lines.extend([
                    f"- **Proposed GA ID:** {result.proposed.analyzer_id}",
                    f"- **Base Analyzer:** {result.proposed.base_analyzer_id}",
                ])
            lines.append("")
            lines.append("| Severity | Category | Message | Action |")
            lines.append("|----------|----------|---------|--------|")
            # Sort unique findings by severity
            unique.sort(key=lambda f: _SEVERITY_ORDER.get(f.severity, 99))
            for f in unique:
                sev = _SEVERITY_LABEL.get(f.severity, str(f.severity))
                lines.append(
                    f"| {sev} | {f.category} | {f.message} | {f.recommended_action or '—'} |"
                )
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# App integration checklist
# ---------------------------------------------------------------------------

def generate_app_checklist(run: MigrationRun) -> str:
    """Generate an app-change checklist developers can follow."""
    lines = [
        "# App Integration Checklist",
        "",
        "Use this checklist after GA analyzers are created.",
        "",
    ]
    for result in run.results:
        if not result.proposed:
            continue
        lines.append(f"## {result.source.analyzer_id} → {result.proposed.analyzer_id}")
        lines.append("")
        lines.append(f"- [ ] Update analyzer ID in app config to `{result.proposed.analyzer_id}`")
        lines.append("- [ ] Update API version to GA (`2025-11-01`)")
        lines.append("- [ ] Replace `analyze` inline content calls with `analyzeBinary`")
        lines.append(f"- [ ] Verify model deployments: `{', '.join(result.proposed.models.keys())}`")

        not_supported = [f for f in result.findings if f.severity == FindingSeverity.NOT_SUPPORTED]
        if not_supported:
            lines.append("- [ ] Address removed features:")
            for f in not_supported:
                lines.append(f"  - {f.message}")

        review = [f for f in result.findings if f.severity == FindingSeverity.NEEDS_REVIEW]
        if review:
            lines.append("- [ ] Review flagged items:")
            for f in review:
                lines.append(f"  - {f.message}")

        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Write all reports
# ---------------------------------------------------------------------------

def write_reports(run: MigrationRun, output_dir: Path) -> list[Path]:
    """Write all report files to the output directory. Returns paths written."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    report_path = output_dir / "migration_report.md"
    report_path.write_text(generate_report(run), encoding="utf-8")
    written.append(report_path)

    checklist_path = output_dir / "app_checklist.md"
    checklist_path.write_text(generate_app_checklist(run), encoding="utf-8")
    written.append(checklist_path)

    return written
