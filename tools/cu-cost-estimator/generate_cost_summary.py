#!/usr/bin/env python3
"""
Cost Summary Generator for CU Analyzer Results

This script processes batch results from Azure Content Understanding analyzer and
generates a comprehensive cost analysis summary including:
- Total cost for the batch
- Cost per document
- Cost breakdown by component
- Recommendations for cost optimization

Usage:
    python generate_cost_summary.py <results_directory> [--model MODEL] [--json] [--output FILE]

Examples:
    # Generate summary for batch results
    python generate_cost_summary.py "Issues/MyProject/results/"
    
    # Save as JSON
    python generate_cost_summary.py "Issues/MyProject/results/" --json --output costs.json
    
    # Specify model used
    python generate_cost_summary.py "Issues/MyProject/results/" --model gpt-4o-mini
"""

import json
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import glob

# Import cost estimator
sys.path.insert(0, str(Path(__file__).parent / "cu-cost-estimator"))
from cost_estimator import CostEstimator, ProcessingRequest, UsageData, extract_usage_from_cu_output


def generate_cost_summary(
    results_directory: str,
    model: str = "gpt-4o-mini",
    deployment: str = "global",
    output_format: str = "text"
) -> Dict[str, Any]:
    """
    Generate cost summary from a directory of CU analyzer results.
    
    Args:
        results_directory: Path to directory containing result JSON files
        model: Model name used for analysis (default: gpt-4o-mini)
        deployment: Deployment type (default: global)
        output_format: Output format - 'text' or 'json'
        
    Returns:
        Dictionary with cost analysis results
    """
    results_path = Path(results_directory)
    if not results_path.exists():
        raise FileNotFoundError(f"Results directory not found: {results_directory}")
    
    # Find all JSON result files
    json_files = list(results_path.glob("*.json")) + list(results_path.glob("**/*.json"))
    if not json_files:
        raise ValueError(f"No JSON files found in {results_directory}")
    
    print(f"Processing {len(json_files)} result files from {results_directory}")
    print()
    
    # Extract usage data from each file
    all_usage = []
    errors = []
    
    for json_file in json_files:
        try:
            usage_dict = extract_usage_from_cu_output(str(json_file))
            usage_dict['filename'] = json_file.name
            all_usage.append(usage_dict)
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            errors.append((json_file.name, str(e)))
    
    if not all_usage:
        raise ValueError(f"Could not extract usage data from any files. Errors:\n" + 
                       "\n".join(f"  {f}: {e}" for f, e in errors))
    
    if errors:
        print(f"Warning: Could not process {len(errors)} files:")
        for filename, error in errors[:5]:  # Show first 5 errors
            print(f"  - {filename}: {error}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more")
        print()
    
    # Aggregate statistics
    total_input_tokens = sum(u['input_tokens'] for u in all_usage)
    total_output_tokens = sum(u['output_tokens'] for u in all_usage)
    total_ctx_tokens = sum(u['contextualization_tokens'] for u in all_usage)
    total_pages = sum(u['document_pages'] for u in all_usage)
    
    # Calculate cost using the estimator
    estimator = CostEstimator()
    usage = UsageData(
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        contextualization_tokens=total_ctx_tokens,
        document_pages_standard=total_pages
    )
    
    request = ProcessingRequest(
        file_type="document",
        quantity=total_pages,
        model_name=model,
        deployment_type=deployment,
        usage_data=usage
    )
    
    breakdown = estimator.estimate_from_usage(request, scale_factor=1.0)
    
    # Prepare summary
    summary = {
        "batch_summary": {
            "total_documents": len(all_usage),
            "total_pages": total_pages,
            "successfully_processed": len(all_usage),
            "failed_to_process": len(errors)
        },
        "usage_summary": {
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_contextualization_tokens": total_ctx_tokens,
            "avg_input_tokens_per_doc": round(total_input_tokens / len(all_usage), 2),
            "avg_output_tokens_per_doc": round(total_output_tokens / len(all_usage), 2),
            "avg_pages_per_doc": round(total_pages / len(all_usage), 2)
        },
        "cost_breakdown": {
            "content_extraction": round(breakdown.ce_cost, 6),
            "field_extraction": round(breakdown.fe_cost, 6),
            "contextualization": round(breakdown.ctx_cost, 6),
            "embeddings": round(breakdown.embeddings_cost, 6),
            "total_cost": round(breakdown.total_cost, 6)
        },
        "cost_per_document": round(breakdown.total_cost / len(all_usage), 6),
        "cost_per_page": round(breakdown.total_cost / total_pages if total_pages > 0 else 0, 6),
        "model_used": model,
        "deployment_type": deployment,
        "estimation_mode": breakdown.estimation_mode
    }
    
    return summary


def print_cost_summary_text(summary: Dict[str, Any]) -> None:
    """Print cost summary in human-readable format."""
    print("=" * 70)
    print("COST ANALYSIS SUMMARY")
    print("=" * 70)
    print()
    
    print("BATCH INFORMATION")
    print("-" * 70)
    batch = summary['batch_summary']
    print(f"  Total Documents:        {batch['total_documents']:,}")
    print(f"  Total Pages Processed:  {batch['total_pages']:,}")
    print(f"  Successfully Processed: {batch['successfully_processed']:,}")
    if batch['failed_to_process'] > 0:
        print(f"  Failed to Process:      {batch['failed_to_process']:,}")
    print()
    
    print("TOTAL COST ESTIMATE")
    print("-" * 70)
    cost = summary['cost_breakdown']
    print(f"  Content Extraction:     ${cost['content_extraction']:.6f}")
    print(f"  Field Extraction (AI):  ${cost['field_extraction']:.6f}")
    print(f"  Contextualization:      ${cost['contextualization']:.6f}")
    if cost['embeddings'] > 0:
        print(f"  Embeddings:             ${cost['embeddings']:.6f}")
    print(f"  {'─' * 66}")
    print(f"  TOTAL COST:             ${cost['total_cost']:.6f}")
    print()
    
    print("PER-UNIT COSTS")
    print("-" * 70)
    print(f"  Per Document:           ${summary['cost_per_document']:.6f}")
    print(f"  Per Page:               ${summary['cost_per_page']:.6f}")
    print()
    
    print("CONFIGURATION")
    print("-" * 70)
    print(f"  Model:                  {summary['model_used']}")
    print(f"  Deployment:             {summary['deployment_type']}")
    print(f"  Estimation Mode:        {summary['estimation_mode']}")
    print()
    
    print("TOKEN USAGE")
    print("-" * 70)
    usage = summary['usage_summary']
    print(f"  Total Input Tokens:     {usage['total_input_tokens']:,}")
    print(f"  Total Output Tokens:    {usage['total_output_tokens']:,}")
    print(f"  Total Ctx Tokens:       {usage['total_contextualization_tokens']:,}")
    print(f"  Avg Input/Doc:          {usage['avg_input_tokens_per_doc']:,.0f}")
    print(f"  Avg Output/Doc:         {usage['avg_output_tokens_per_doc']:,.0f}")
    print()


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Generate cost analysis summary for CU analyzer batch results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_cost_summary.py "Issues/MyProject/results/"
  python generate_cost_summary.py "Issues/MyProject/results/" --model gpt-4o-mini --json
  python generate_cost_summary.py "Issues/MyProject/results/" --output costs.json
        """
    )
    
    parser.add_argument("results_directory",
                       help="Path to directory containing CU analyzer result JSON files")
    parser.add_argument("--model", default="gpt-4o-mini",
                       help="Model used for analysis (default: gpt-4o-mini)")
    parser.add_argument("--deployment", default="global",
                       choices=["global", "regional", "data_zone", "ptu"],
                       help="Deployment type (default: global)")
    parser.add_argument("--json", action="store_true",
                       help="Output as JSON instead of human-readable text")
    parser.add_argument("--output", type=str,
                       help="Save output to file (if not specified, prints to stdout)")
    
    args = parser.parse_args()
    
    try:
        summary = generate_cost_summary(
            args.results_directory,
            model=args.model,
            deployment=args.deployment
        )
        
        # Format output
        if args.json:
            output = json.dumps(summary, indent=2)
        else:
            # For text output, print summary and return empty string
            print_cost_summary_text(summary)
            output = ""
        
        # Write to file or stdout
        if args.output:
            with open(args.output, 'w') as f:
                if args.json:
                    f.write(output)
                else:
                    # Reformat for file (already printed above)
                    print(f"Cost summary saved to {args.output}")
        else:
            if args.json:
                print(output)
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
