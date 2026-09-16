#!/usr/bin/env python3
"""Offline usage/pricing coverage for recursive native CLI or saved CU results."""

import argparse
import io
import json
import sys
from contextlib import redirect_stdout
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from cu_cost_estimator import (
    CostEstimator, ProcessingRequest, extract_usage_from_result, usage_data_from_extracted,
)
from cu_result_io import load_results, result_payload, result_status


_COST_KEYS = {
    "content_extraction": "ce_cost",
    "field_extraction": "fe_cost",
    "contextualization": "ctx_cost",
    "embeddings": "embeddings_cost",
    "total_cost": "total_cost",
}


def generate_cost_summary(
    results_directory: str,
    model: Optional[str] = None,
    deployment: str = "global",
    output_format: str = "text",
) -> Dict[str, Any]:
    """Estimate documented usage only, reporting unknown totals and honest coverage.

    Discovery errors fail with a source path. Valid but empty/failed results and
    results without usable usage stay in ``total_documents``. Full-batch costs
    are null unless every discovered result has both complete usage and pricing.
    ``covered_cost_breakdown`` is a separately labelled partial estimate, never
    actual spend. CLI reports/manifests are not analysis inputs: attempted inputs
    lacking result files are outside this loader's denominator.

    ``model`` is optional only when token keys identify one priced model. It
    cannot silently reprice a different or mixed measured model. ``output_format``
    is retained for compatibility; this function never prints.
    """
    results = load_results(results_directory)
    if not results:
        raise ValueError(f"No analysis results found in {results_directory}")
    estimator = CostEstimator()
    estimator.get_pricing_tier(deployment)
    documents = []
    all_usage = []
    covered = []
    used_models = set()
    for result in results:
        metadata = result["_metadata"]
        document = {
            "result_file": metadata["result_file"],
            "document": metadata.get("document", metadata.get("source_file")),
            "status": result_status(result),
            "usage_available": False,
            "cost_estimate": None,
            "error": None,
        }
        try:
            usage_dict = extract_usage_from_result(result)
            usage = usage_data_from_extracted(usage_dict)
            document["usage_available"] = True
            document["usage"] = usage_dict
            all_usage.append(usage_dict)
            models = usage_dict["models"]
            if len(models) > 1:
                raise ValueError("Multiple measured models require separate per-model pricing")
            if model and models and models != [model]:
                raise ValueError(f"Requested model {model} differs from measured model {models[0]}")
            selected_model = model or (models[0] if models else None)
            if not selected_model:
                raise ValueError("Model pricing is unknown; provide --model explicitly")
            used_models.add(selected_model)
            request = ProcessingRequest(
                file_type="document",
                quantity=usage_dict["document_pages"],
                model_name=selected_model,
                deployment_type=deployment,
                usage_data=usage,
            )
            breakdown = estimator.estimate_from_usage(request)
            covered.append(asdict(breakdown))
            document["cost_estimate"] = round(breakdown.total_cost, 6)
            document["model"] = selected_model
        except (ValueError, KeyError) as exc:
            document["error"] = str(exc)
        documents.append(document)

    total = len(results)
    complete_usage = len(all_usage) == total
    complete_cost = len(covered) == total
    covered_cost = {
        key: round(sum(item[value] for item in covered), 6) if covered else None
        for key, value in _COST_KEYS.items()
    }
    cost = covered_cost if complete_cost else {key: None for key in _COST_KEYS}
    usage_totals = {
        "total_input_tokens": "input_tokens",
        "total_output_tokens": "output_tokens",
        "total_contextualization_tokens": "contextualization_tokens",
        "total_pages": "document_pages",
    }
    measured = {
        key: sum(item[value] for item in all_usage) if all_usage else None
        for key, value in usage_totals.items()
    }
    batch_pages = measured["total_pages"] if complete_usage else None
    statuses = [str(item["status"] or "").lower() for item in documents]
    return {
        "batch_summary": {
            "total_documents": total,
            "total_pages": batch_pages,
            "successfully_processed": statuses.count("succeeded"),
            "failed_to_process": sum(status in {"failed", "canceled", "cancelled"} for status in statuses),
            "status_unknown": statuses.count(""),
            "incomplete_results": sum(
                not result_payload(result).get("contents") and not result_payload(result).get("fields")
                for result in results
            ),
        },
        "coverage": {
            "results_with_usage": len(all_usage),
            "results_without_usable_usage": total - len(all_usage),
            "results_with_cost_estimate": len(covered),
            "usage_percent": round(len(all_usage) / total * 100, 1),
            "cost_percent": round(len(covered) / total * 100, 1),
            "complete": complete_cost,
            "denominator": "Discovered analysis result files only; reports and manifests excluded",
        },
        "usage_summary": {
            **{key: value if complete_usage else None for key, value in measured.items()},
            "avg_input_tokens_per_doc": round(measured["total_input_tokens"] / total, 2) if complete_usage else None,
            "avg_output_tokens_per_doc": round(measured["total_output_tokens"] / total, 2) if complete_usage else None,
            "avg_pages_per_doc": round(batch_pages / total, 2) if complete_usage else None,
        },
        "covered_usage_summary": measured,
        "cost_breakdown": cost,
        "covered_cost_breakdown": covered_cost,
        "cost_per_document": round(cost["total_cost"] / total, 6) if complete_cost else None,
        "cost_per_page": round(cost["total_cost"] / batch_pages, 6) if complete_cost and batch_pages else None,
        "model_used": model or (next(iter(used_models)) if len(used_models) == 1 else None),
        "deployment_type": deployment,
        "estimation_mode": "usage_based" if complete_cost else "partial_usage_based" if covered else "unknown",
        "pricing_note": (
            "Estimated pricing scenario using bundled illustrative rates, not actual spend. "
            "Verify current contract/region/model rates. PTU capacity charges, discounts and "
            "unrecorded usage are excluded. Native CLI results may omit usage and timing."
        ),
        "documents": documents,
    }


def print_cost_summary_text(summary: Dict[str, Any]) -> None:
    """Print estimates without formatting missing values as zero."""
    def number(value: Any, *, money: bool = False) -> str:
        if value is None:
            return "unknown"
        return f"${value:.6f}" if money else f"{value:,}"

    batch = summary["batch_summary"]
    coverage = summary["coverage"]
    print("OFFLINE COST ESTIMATE (not actual spend)")
    print(f"Result files: {batch['total_documents']}")
    print(f"Recorded succeeded / failed / unknown: {batch['successfully_processed']} / "
          f"{batch['failed_to_process']} / {batch['status_unknown']}")
    print(f"Usage coverage: {coverage['results_with_usage']}/{batch['total_documents']}")
    print(f"Pricing coverage: {coverage['results_with_cost_estimate']}/{batch['total_documents']}")
    print(f"Full-batch estimate: {number(summary['cost_breakdown']['total_cost'], money=True)}")
    print(f"Covered subset estimate: {number(summary['covered_cost_breakdown']['total_cost'], money=True)}")
    for key, value in summary["cost_breakdown"].items():
        if key != "total_cost":
            print(f"  {key}: {number(value, money=True)}")
    print(f"Per document: {number(summary['cost_per_document'], money=True)}")
    print(f"Per page: {number(summary['cost_per_page'], money=True)}")
    print(summary["pricing_note"])
    print(coverage["denominator"])
    for document in summary["documents"]:
        if document["error"]:
            print(f"  {document['result_file']}: {document['error']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_directory", help="Result directory (recursive) or explicit JSON result")
    parser.add_argument("--model", help="Model pricing; otherwise use measured token model names")
    parser.add_argument("--deployment", default="global", choices=["global", "regional", "data_zone", "ptu"])
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    parser.add_argument("--output", help="Save JSON or text output")
    args = parser.parse_args()
    try:
        summary = generate_cost_summary(args.results_directory, args.model, args.deployment)
        if args.json:
            output = json.dumps(summary, indent=2)
        else:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                print_cost_summary_text(summary)
            output = buffer.getvalue().rstrip()
        if args.output:
            destination = Path(args.output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(output + "\n", encoding="utf-8")
        else:
            print(output)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
