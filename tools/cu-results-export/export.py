# =============================================================================
# Tool: cu-results-export
# Status: ✅ IMPLEMENTED - Export CU results to CSV/Excel with wide table format
# Last Tested: 2026-01-26
# =============================================================================
"""
CU Results Export Tool

Export Content Understanding analysis results to CSV or Excel format.
Flattens JSON results into a wide table with:
- Rows: document × iteration
- Columns: metadata fields + one column per extracted field

Usage:
    # Export to CSV
    python export.py --input results/ --output results.csv
    
    # Export to Excel
    python export.py --input results/ --output results.xlsx
    
    # Include specific fields only
    python export.py --input results/ --output results.csv --fields InvoiceNumber,InvoiceDate,Total
"""

import argparse
import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


def load_results(input_path: Path) -> List[Dict[str, Any]]:
    """Load all JSON result files from input path."""
    results = []
    
    if input_path.is_file() and input_path.suffix == ".json":
        with open(input_path, "r", encoding="utf-8") as f:
            results.append(json.load(f))
    elif input_path.is_dir():
        # Look for results in the directory and results/ subdirectory
        search_paths = [input_path]
        if (input_path / "results").exists():
            search_paths.append(input_path / "results")
        
        for search_path in search_paths:
            for json_file in sorted(search_path.glob("*.json")):
                # Skip metadata.json
                if json_file.name == "metadata.json":
                    continue
                # Skip layout results
                if ".layout." in json_file.name:
                    continue
                    
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        result = json.load(f)
                        # Add source file info if not present
                        if "_metadata" not in result:
                            result["_metadata"] = {}
                        if "source_file" not in result["_metadata"]:
                            result["_metadata"]["source_file"] = json_file.name
                        results.append(result)
                except json.JSONDecodeError as e:
                    print(f"Warning: Could not parse {json_file}: {e}")
    
    return results


def extract_fields_from_result(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract field values from a CU result.
    
    Returns a list of dicts, one per content entry. Each dict includes a
    '_category' key (empty string for non-classified results) and all
    flattened field values.  For backwards compatibility with callers that
    expect a single dict, use ``extract_fields_from_result(r)[0]`` or the
    helper ``extract_fields_flat(r)``.
    """
    entries: List[Dict[str, Any]] = []
    result_data = result.get("result", {})
    
    # Check for fields directly on result (non-classified)
    if "fields" in result_data:
        entry = {"_category": ""}
        entry.update(flatten_fields(result_data["fields"]))
        entries.append(entry)
    
    # Check for fields in contents array (may include category for classify-and-route)
    contents = result_data.get("contents", [])
    for content in contents:
        if "fields" in content:
            entry = {"_category": content.get("category", "")}
            entry.update(flatten_fields(content["fields"]))
            entries.append(entry)
    
    # Fallback: return at least one empty entry so callers don't break
    if not entries:
        entries.append({"_category": ""})
    
    return entries


def extract_fields_flat(result: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy helper: merge all content entries into a single flat dict."""
    merged: Dict[str, Any] = {}
    for entry in extract_fields_from_result(result):
        cat = entry.pop("_category", "")
        if cat:
            # Prefix fields with category to avoid collisions across categories
            for k, v in entry.items():
                merged[f"{cat}.{k}"] = v
        else:
            merged.update(entry)
    return merged


def flatten_fields(fields: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Flatten nested field structure to simple key-value pairs."""
    flat = {}
    
    for field_name, field_data in fields.items():
        full_name = f"{prefix}{field_name}" if prefix else field_name
        
        if isinstance(field_data, dict):
            # Check if this is a CU field object with 'value' key
            if "value" in field_data:
                value = field_data["value"]
                
                # Handle different value types
                if isinstance(value, dict):
                    # Nested object - flatten it
                    flat.update(flatten_fields(value, f"{full_name}."))
                elif isinstance(value, list):
                    # Array - serialize to JSON string for now
                    flat[full_name] = json.dumps(value)
                else:
                    # Simple value
                    flat[full_name] = value
            elif "values" in field_data:
                # Array field with 'values' key
                flat[full_name] = json.dumps(field_data["values"])
            else:
                # Nested object without 'value' - recurse
                flat.update(flatten_fields(field_data, f"{full_name}."))
        else:
            # Direct value
            flat[full_name] = field_data
    
    return flat


def discover_all_fields(results: List[Dict[str, Any]]) -> List[str]:
    """Discover all unique field names across all results."""
    all_fields: Set[str] = set()
    
    for result in results:
        fields = extract_fields_flat(result)
        all_fields.update(fields.keys())
    
    return sorted(all_fields)


def build_table_rows(
    results: List[Dict[str, Any]], 
    field_columns: List[str]
) -> List[Dict[str, Any]]:
    """Build table rows from results.
    
    For classify-and-route results with multiple content entries, produces
    one row per category (each row shares the same document metadata but
    has its own category label and field values).
    """
    rows = []
    
    for result in results:
        # Extract metadata
        metadata = result.get("_metadata", {})
        
        base_row = {
            "run_id": metadata.get("run_id", ""),
            "document": metadata.get("document", metadata.get("source_file", "")),
            "iteration": metadata.get("iteration", 1),
            "timestamp": metadata.get("timestamp", ""),
            "analyzer_id": metadata.get("analyzer_id", ""),
        }
        
        entries = extract_fields_from_result(result)
        
        # Check if any entry has a category (classify-and-route result)
        has_categories = any(e.get("_category") for e in entries)
        
        for entry in entries:
            row = dict(base_row)
            category = entry.pop("_category", "")
            
            if has_categories:
                row["category"] = category
                # For classified results, prefix field names with category
                for field_name in field_columns:
                    prefixed = f"{category}.{field_name}" if category else field_name
                    row[field_name] = entry.get(field_name, entry.get(prefixed, ""))
            else:
                row["category"] = ""
                for field_name in field_columns:
                    row[field_name] = entry.get(field_name, "")
            
            rows.append(row)
    
    return rows


def export_to_csv(rows: List[Dict[str, Any]], output_path: Path, field_columns: List[str]):
    """Export rows to CSV file."""
    # Define column order: metadata first, then fields
    metadata_cols = ["run_id", "document", "category", "iteration", "timestamp", "analyzer_id"]
    all_columns = metadata_cols + field_columns
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns)
        writer.writeheader()
        writer.writerows(rows)


def export_to_excel(rows: List[Dict[str, Any]], output_path: Path, field_columns: List[str]):
    """Export rows to Excel file."""
    if not HAS_OPENPYXL:
        raise ImportError("openpyxl is required for Excel export. Install with: pip install openpyxl")
    
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"
    
    # Define column order
    metadata_cols = ["run_id", "document", "category", "iteration", "timestamp", "analyzer_id"]
    all_columns = metadata_cols + field_columns
    
    # Header styling
    header_font = Font(bold=True)
    header_fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
    
    # Write headers
    for col_idx, col_name in enumerate(all_columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
    
    # Write data
    for row_idx, row_data in enumerate(rows, 2):
        for col_idx, col_name in enumerate(all_columns, 1):
            value = row_data.get(col_name, "")
            ws.cell(row=row_idx, column=col_idx, value=value)
    
    # Auto-adjust column widths
    for col_idx, col_name in enumerate(all_columns, 1):
        max_length = len(col_name)
        for row_idx in range(2, len(rows) + 2):
            cell_value = str(ws.cell(row=row_idx, column=col_idx).value or "")
            max_length = max(max_length, min(len(cell_value), 50))
        ws.column_dimensions[get_column_letter(col_idx)].width = max_length + 2
    
    # Freeze header row
    ws.freeze_panes = "A2"
    
    wb.save(output_path)


def generate_summary(rows: List[Dict[str, Any]], field_columns: List[str]) -> Dict[str, Any]:
    """Generate summary statistics for the export."""
    summary = {
        "total_rows": len(rows),
        "unique_documents": len(set(r["document"] for r in rows)),
        "unique_runs": len(set(r["run_id"] for r in rows if r["run_id"])),
        "field_count": len(field_columns),
        "fields": field_columns,
        "fill_rates": {}
    }
    
    # Calculate fill rate for each field
    for field in field_columns:
        filled = sum(1 for r in rows if r.get(field) not in (None, "", []))
        summary["fill_rates"][field] = round(filled / len(rows) * 100, 1) if rows else 0
    
    return summary


# ===========================================================================
# Confidence extraction & field diagnosis (--diagnose)
# ===========================================================================

def extract_confidence_from_fields(fields: Dict[str, Any], prefix: str = "") -> Dict[str, float]:
    """Extract confidence scores from CU result fields.
    
    Handles both CU native format (valueString/valueNumber + confidence)
    and preprocessed format (value + confidence). Returns flat map of
    field_name -> confidence for scalar fields only.
    """
    confidences: Dict[str, float] = {}
    
    for field_name, field_data in fields.items():
        full_name = f"{prefix}{field_name}" if prefix else field_name
        
        if not isinstance(field_data, dict):
            continue
        
        confidence = field_data.get("confidence")
        
        # Check if this is a CU field node (has valueString/valueNumber/etc or value)
        has_value = any(k.startswith("value") for k in field_data) or "value" in field_data
        
        if has_value and confidence is not None:
            # Check for nested object value (valueObject)
            value_obj = field_data.get("valueObject")
            if isinstance(value_obj, dict):
                # Recurse into object fields
                confidences.update(extract_confidence_from_fields(value_obj, f"{full_name}."))
            else:
                confidences[full_name] = float(confidence)
        elif "fields" in field_data:
            # Nested group (e.g. classify-and-route content)
            confidences.update(extract_confidence_from_fields(field_data["fields"], f"{full_name}."))
        elif not has_value and confidence is None:
            # Plain nested object — recurse
            confidences.update(extract_confidence_from_fields(field_data, f"{full_name}."))
    
    return confidences


def extract_all_confidences(results: List[Dict[str, Any]]) -> List[Dict[str, float]]:
    """Extract confidence maps from all results, handling classify-and-route."""
    all_confs = []
    
    for result in results:
        result_data = result.get("result", {})
        
        # Direct fields
        if "fields" in result_data:
            all_confs.append(extract_confidence_from_fields(result_data["fields"]))
        
        # Classify-and-route contents
        for content in result_data.get("contents", []):
            if "fields" in content:
                category = content.get("category", "")
                conf_map = extract_confidence_from_fields(content["fields"])
                if category:
                    conf_map = {f"{category}.{k}": v for k, v in conf_map.items()}
                all_confs.append(conf_map)
    
    return all_confs


def _median(values: List[float]) -> float:
    """Compute median of a list of floats."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 0:
        return (s[n // 2 - 1] + s[n // 2]) / 2
    return s[n // 2]


def _stdev(values: List[float]) -> Optional[float]:
    """Compute sample standard deviation. Returns None if n < 2."""
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return math.sqrt(variance)


def diagnose_fields(
    results: List[Dict[str, Any]],
    field_columns: List[str],
    fill_rates: Dict[str, float],
) -> List[Dict[str, Any]]:
    """Generate per-field diagnostics with actionable suggestions.
    
    Works at the CU field level (not the flattened export column level).
    Extracts confidence from raw results and computes fill rate from 
    value presence.
    
    Args:
        results: Raw CU result dicts
        field_columns: Field names from export (used as fallback)
        fill_rates: Pre-computed fill rates from generate_summary (%)
    
    Returns:
        List of diagnostic dicts, one per field, sorted by severity.
    """
    all_confs = extract_all_confidences(results)
    
    # Discover CU-level field names from confidence maps
    cu_field_names: Set[str] = set()
    for conf_map in all_confs:
        cu_field_names.update(conf_map.keys())
    
    # Also discover from raw results (fields that have values but maybe no confidence)
    for result in results:
        result_data = result.get("result", {})
        if "fields" in result_data:
            cu_field_names.update(_discover_cu_fields(result_data["fields"]))
        for content in result_data.get("contents", []):
            if "fields" in content:
                category = content.get("category", "")
                names = _discover_cu_fields(content["fields"])
                if category:
                    cu_field_names.update(f"{category}.{n}" for n in names)
                else:
                    cu_field_names.update(names)
    
    if not cu_field_names:
        # Fallback to export columns
        cu_field_names = set(field_columns)
    
    total_docs = len(all_confs) if all_confs else len(results)
    
    # Compute fill rate at CU field level
    cu_fill_rates = _compute_cu_fill_rates(results, cu_field_names)
    
    diagnostics = []
    
    for field in sorted(cu_field_names):
        # Collect confidence values where field is present
        conf_values = []
        for conf_map in all_confs:
            if field in conf_map:
                conf_values.append(conf_map[field])
        
        fill_rate = cu_fill_rates.get(field, 0.0)
        present_count = len(conf_values)
        conf_median = _median(conf_values) if conf_values else None
        conf_min = min(conf_values) if conf_values else None
        conf_stdev = _stdev(conf_values) if len(conf_values) >= 5 else None
        
        # Generate suggestions
        suggestions = []
        severity = "ok"
        
        if fill_rate < 50:
            suggestions.append("Very low fill rate — field may not exist in these documents or description doesn't match")
            severity = "critical"
        elif fill_rate < 80:
            suggestions.append("Low fill rate — check field description specificity or document coverage")
            severity = "warning"
        
        if conf_median is not None and conf_median < 0.5:
            suggestions.append("Very low confidence — field description likely needs major revision")
            severity = "critical"
        elif conf_median is not None and conf_median < 0.7:
            suggestions.append("Low confidence — improve description with location hints and alternative labels")
            if severity != "critical":
                severity = "warning"
        
        if conf_stdev is not None and conf_stdev > 0.15:
            suggestions.append("High variance — field may be ambiguous across document variations")
            if severity == "ok":
                severity = "info"
        
        if conf_min is not None and conf_min < 0.3 and (conf_median or 0) > 0.7:
            suggestions.append("Outlier detected — some documents have very low confidence for this field")
            if severity == "ok":
                severity = "info"
        
        diagnostics.append({
            "field": field,
            "fill_rate": fill_rate,
            "present_count": present_count,
            "total_docs": total_docs,
            "confidence_median": round(conf_median, 3) if conf_median is not None else None,
            "confidence_min": round(conf_min, 3) if conf_min is not None else None,
            "confidence_stdev": round(conf_stdev, 3) if conf_stdev is not None else None,
            "severity": severity,
            "suggestions": suggestions,
        })
    
    # Sort: critical first, then warning, then info, then ok
    severity_order = {"critical": 0, "warning": 1, "info": 2, "ok": 3}
    diagnostics.sort(key=lambda d: (severity_order.get(d["severity"], 4), -d["fill_rate"]))
    
    return diagnostics


def _discover_cu_fields(fields: Dict[str, Any], prefix: str = "") -> List[str]:
    """Discover CU-level field names (not flattened properties)."""
    names = []
    for field_name, field_data in fields.items():
        full_name = f"{prefix}{field_name}" if prefix else field_name
        if not isinstance(field_data, dict):
            continue
        # CU field node has type or value* keys
        has_type = "type" in field_data
        has_value = any(k.startswith("value") for k in field_data) or "value" in field_data
        if has_type or has_value:
            names.append(full_name)
            # Recurse into valueObject
            value_obj = field_data.get("valueObject")
            if isinstance(value_obj, dict):
                names.extend(_discover_cu_fields(value_obj, f"{full_name}."))
        elif "fields" in field_data:
            names.extend(_discover_cu_fields(field_data["fields"], f"{full_name}."))
    return names


def _compute_cu_fill_rates(results: List[Dict[str, Any]], field_names: Set[str]) -> Dict[str, float]:
    """Compute fill rate at the CU field level (value presence, not property presence)."""
    total = 0
    field_counts: Dict[str, int] = {f: 0 for f in field_names}
    
    for result in results:
        result_data = result.get("result", {})
        
        if "fields" in result_data:
            total += 1
            present = set(_discover_cu_fields(result_data["fields"]))
            for f in field_names:
                if f in present:
                    field_counts[f] += 1
        
        for content in result_data.get("contents", []):
            if "fields" in content:
                total += 1
                category = content.get("category", "")
                present = set(_discover_cu_fields(content["fields"]))
                if category:
                    present = {f"{category}.{n}" for n in present}
                for f in field_names:
                    if f in present:
                        field_counts[f] += 1
    
    if total == 0:
        return {f: 0.0 for f in field_names}
    return {f: round(c / total * 100, 1) for f, c in field_counts.items()}


def print_diagnosis(diagnostics: List[Dict[str, Any]]) -> None:
    """Print formatted diagnostic report to stdout."""
    print("\n" + "=" * 70)
    print("FIELD DIAGNOSIS")
    print("=" * 70)
    
    severity_icons = {"critical": "🔴", "warning": "🟡", "info": "🔵", "ok": "🟢"}
    
    issues_found = sum(1 for d in diagnostics if d["severity"] != "ok")
    print(f"\nFields analyzed: {len(diagnostics)}")
    print(f"Issues found: {issues_found}")
    
    if not issues_found:
        print("\n✅ All fields look healthy!")
        return
    
    print(f"\n{'Field':<30} {'Fill%':>6} {'Conf':>6} {'Min':>6} {'Status':>8}")
    print("-" * 70)
    
    for d in diagnostics:
        icon = severity_icons.get(d["severity"], " ")
        conf_str = f"{d['confidence_median']:.2f}" if d["confidence_median"] is not None else "N/A"
        min_str = f"{d['confidence_min']:.2f}" if d["confidence_min"] is not None else "N/A"
        field_display = d["field"][:28]
        print(f"{icon} {field_display:<28} {d['fill_rate']:>5.1f}% {conf_str:>6} {min_str:>6} {d['severity']:>8}")
    
    # Print suggestions for problematic fields
    problem_fields = [d for d in diagnostics if d["suggestions"]]
    if problem_fields:
        print(f"\n{'Suggestions':}")
        print("-" * 70)
        for d in problem_fields:
            for suggestion in d["suggestions"]:
                print(f"  {d['field']}: {suggestion}")


def main():
    parser = argparse.ArgumentParser(
        description="Export CU analysis results to CSV or Excel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all results to CSV
  python export.py --input results/ --output results.csv
  
  # Export to Excel
  python export.py --input results/ --output results.xlsx
  
  # Export specific fields only
  python export.py --input results/ --output results.csv --fields InvoiceNumber,InvoiceDate,Total
  
  # Show summary without exporting
  python export.py --input results/ --summary-only
        """
    )
    
    parser.add_argument("--input", "-i", required=True, help="Input directory with JSON results or single JSON file")
    parser.add_argument("--output", "-o", help="Output file path (.csv or .xlsx)")
    parser.add_argument("--fields", "-f", help="Comma-separated list of fields to include (default: all)")
    parser.add_argument("--summary-only", action="store_true", help="Only print summary, don't export")
    parser.add_argument("--diagnose", action="store_true", help="Run field diagnostics (confidence analysis + suggestions)")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        print(f"Error: Input path does not exist: {input_path}")
        sys.exit(1)
    
    # Load results
    print(f"Loading results from: {input_path}")
    results = load_results(input_path)
    
    if not results:
        print("Error: No results found")
        sys.exit(1)
    
    print(f"Loaded {len(results)} result(s)")
    
    # Discover or filter fields
    all_fields = discover_all_fields(results)
    
    if args.fields:
        requested_fields = [f.strip() for f in args.fields.split(",")]
        field_columns = [f for f in requested_fields if f in all_fields]
        missing = set(requested_fields) - set(field_columns)
        if missing:
            print(f"Warning: Fields not found in results: {missing}")
    else:
        field_columns = all_fields
    
    print(f"Fields to export: {len(field_columns)}")
    
    # Build table rows
    rows = build_table_rows(results, field_columns)
    
    # Generate and print summary
    summary = generate_summary(rows, field_columns)
    print("\n--- Summary ---")
    print(f"Total rows: {summary['total_rows']}")
    print(f"Unique documents: {summary['unique_documents']}")
    print(f"Fields: {summary['field_count']}")
    print("\nFill rates:")
    for field, rate in summary["fill_rates"].items():
        print(f"  {field}: {rate}%")
    
    # Run diagnostics if requested
    if args.diagnose:
        diagnostics = diagnose_fields(results, field_columns, summary["fill_rates"])
        print_diagnosis(diagnostics)
        
        # Save diagnostics JSON
        if args.output:
            diag_path = Path(args.output).with_suffix(".diagnosis.json")
            with open(diag_path, "w", encoding="utf-8") as f:
                json.dump(diagnostics, f, indent=2)
            print(f"\n✓ Diagnostics saved to {diag_path}")
    
    if args.summary_only:
        return
    
    if not args.output:
        print("\nError: --output is required (unless --summary-only)")
        sys.exit(1)
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Export based on file extension
    if output_path.suffix.lower() == ".xlsx":
        print(f"\nExporting to Excel: {output_path}")
        export_to_excel(rows, output_path, field_columns)
    else:
        print(f"\nExporting to CSV: {output_path}")
        export_to_csv(rows, output_path, field_columns)
    
    print(f"✓ Exported {len(rows)} rows to {output_path}")
    
    # Save summary JSON alongside export
    summary_path = output_path.with_suffix(".summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"✓ Summary saved to {summary_path}")


if __name__ == "__main__":
    main()
