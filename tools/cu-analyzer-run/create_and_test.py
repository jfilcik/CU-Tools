# =============================================================================
# Tool: cu-analyzer-run/create_and_test.py
# Status: ✅ UPDATED - Schema development workflow with validation
# Last Updated: 2026-01-28
# =============================================================================
"""
CU Analyzer Create and Test Tool - Schema Development Workflow

✨ Use this tool when:
  - You have a SCHEMA FILE to test
  - You're developing/iterating on a schema
  - You want automatic validation before creating analyzer
  - You want automatic cleanup after testing

🔧 For production use with existing analyzers, use run.py instead:
  - When you already have an analyzer ID
  - For layout extraction (first step)
  - For batch processing in production

Workflow:
1. Validates analyzer schema (catches errors early)
2. Loads schema from file
3. Creates analyzer in Azure AI
4. Waits for analyzer to be ready
5. Runs test analysis on sample documents
6. Optionally cleans up analyzer after testing

Usage:
    # Basic: Create, test, and clean up
    python create_and_test.py \
      --schema schemas/invoice_v2.json \
      --input samples/ \
      --output test_results/v2/
    
    # With parallel processing (3 workers - faster!)
    python create_and_test.py \
      --schema schemas/invoice_v2.json \
      --input samples/ \
      --output test_results/v2/ \
      --max-workers 3
    
    # Keep analyzer after testing (for production use)
    python create_and_test.py \
      --schema schemas/invoice_v2.json \
      --input samples/ \
      --output test_results/ \
      --keep-analyzer
    
    # Stability test (10 iterations per document)
    python create_and_test.py \
      --schema schemas/invoice_v2.json \
      --input samples/ \
      --output test_results/stability/ \
      --iterations 10
    
    # Classify-and-route: create inner analyzers + classifier + test
    python create_and_test.py \
      --schema schemas/classifier_v1.json \
      --inner-schema vehicle_title=schemas/title_extractor_v1.json \
      --inner-schema vehicle_registration=schemas/reg_extractor_v1.json \
      --input samples/ \
      --output test_results/classify_route_v1/

Typical Development Cycle:
    1. Extract layout: python run.py --layout --input samples/ --output layout/
    2. Create schema based on layout files
    3. Test schema: python create_and_test.py --schema schema.json --input samples/ --output results/
    4. Review results, iterate on schema (repeat step 3)
    5. Keep final version: add --keep-analyzer flag

Note:
    Schema validation runs automatically before creating the analyzer.
    If validation fails, the tool stops and displays error messages.
    
See Also:
    run.py - For production operations with existing analyzers
    ../cu-analyzer-validate/cu_analyzer_validator.py - Standalone schema validation
"""

import argparse
import copy
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "cu-client"))
sys.path.insert(0, str(Path(__file__).parent.parent / "cu-analyzer-validate"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "python"))

from content_understanding_client import AzureContentUnderstandingClient
from dotenv import load_dotenv
import os

# Import validator
try:
    from cu_analyzer_validator import validate_cu_analyzer_file
    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False
    print("⚠️  WARNING: cu_analyzer_validator not found.")
    print("   Schema validation will be skipped.")
    print("   The validator should be in: tools/cu-analyzer-validate/cu_analyzer_validator.py")
    print("   Validation is highly recommended before creating analyzers.")
    validate_cu_analyzer_file = None

# Import existing run.py functions
from run import (
    get_client,
    resolve_api_version,
    get_supported_files,
    check_files_for_protection,
    run_analysis,
    save_result,
    create_run_metadata
)


def validate_schema(
    schema_path: Path,
    strict: bool = False,
    api_version: Optional[str] = None,
) -> bool:
    """
    Validate analyzer schema using cu-analyzer-validate.
    
    Args:
        schema_path: Path to schema JSON file
        strict: If True, warnings are treated as errors
        
    Returns:
        bool: True if valid (and no warnings in strict mode)
    """
    if validate_cu_analyzer_file is None:
        print("  ⚠️  Schema validation skipped (validator not available)")
        print("     It is strongly recommended to validate schemas before creating analyzers")
        return True
    
    print(f"\n{'='*60}")
    print(f"Validating schema: {schema_path.name}")
    print(f"{'='*60}")
    
    result = validate_cu_analyzer_file(str(schema_path), api_version=api_version)
    
    # Print summary
    print(f"\n{result.get_summary()}\n")
    
    # Print errors if any
    if result.errors:
        print("=" * 60)
        print("ERRORS:")
        print("=" * 60)
        for error in result.errors:
            print(f"\n{error}")
        print()
    
    # Print warnings if any
    if result.warnings:
        print("-" * 60)
        print("WARNINGS:")
        print("-" * 60)
        for warning in result.warnings:
            print(f"\n{warning}")
        print()
    
    # In strict mode, warnings are errors
    if strict and result.warnings:
        print("❌ Validation failed: Warnings present in strict mode")
        return False
    
    if not result.is_valid:
        print("❌ Validation failed: Please fix errors before creating analyzer")
        return False
    
    print("✅ Schema validation passed!")
    return True


def load_schema(schema_path: Path) -> dict:
    """Load analyzer schema from JSON file and ensure required fields."""
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    
    # Ensure required fields are present
    if "baseAnalyzerId" not in schema:
        raise ValueError("Schema missing required field: 'baseAnalyzerId'. Add: \"baseAnalyzerId\": \"prebuilt-document\"")
    
    # Add default models if not specified
    if "models" not in schema:
        schema["models"] = {"completion": "gpt-4.1"}
        print(f"  Added default model: gpt-4.1")
    elif "completion" not in schema.get("models", {}):
        schema["models"]["completion"] = "gpt-4.1"
        print(f"  Added default completion model: gpt-4.1")
    
    # Ensure config has required settings
    if "config" not in schema:
        schema["config"] = {}
    if "returnDetails" not in schema["config"]:
        schema["config"]["returnDetails"] = True
    
    # Only add estimateFieldSourceAndConfidence for non-contentCategories schemas
    # (contentCategories schemas delegate field extraction to inner analyzers)
    has_content_categories = "contentCategories" in schema.get("config", {})
    if not has_content_categories:
        if "estimateFieldSourceAndConfidence" not in schema["config"]:
            schema["config"]["estimateFieldSourceAndConfidence"] = True
    
    return schema


def generate_analyzer_id(schema_path: Path) -> str:
    """Generate unique analyzer ID from schema filename and timestamp."""
    # Extract base name without version/extension
    base = schema_path.stem.replace("_", "").replace("-", "").lower()
    # Remove version numbers
    import re
    base = re.sub(r'v\d+(\.\d+)*', '', base)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{base}{timestamp}"[:64]  # Max 64 chars


def create_analyzer(
    client: AzureContentUnderstandingClient,
    analyzer_id: str,
    schema: dict,
    max_wait: int = 120
) -> dict:
    """
    Create analyzer and wait for it to be ready.
    
    Returns:
        dict: Analyzer details once ready
    """
    print(f"\n{'='*60}")
    print(f"Creating analyzer: {analyzer_id}")
    print(f"{'='*60}")
    
    # Try to delete existing analyzer first (in case of retry)
    try:
        client.delete_analyzer(analyzer_id)
        print(f"  Deleted existing analyzer with same ID")
        time.sleep(2)
    except Exception:
        pass  # Analyzer doesn't exist, that's fine
    
    # Create the analyzer
    try:
        response = client.begin_create_analyzer(analyzer_id, analyzer_template=schema)
        print(f"  ✓ Create request accepted")
    except Exception as e:
        print(f"  ✗ Failed to create analyzer: {e}")
        raise
    
    # Poll until analyzer is ready
    print(f"  Waiting for analyzer to be ready (max {max_wait}s)...")
    poll_interval = 3
    elapsed = 0
    
    while elapsed < max_wait:
        try:
            detail = client.get_analyzer_detail_by_id(analyzer_id)
            status = detail.get("status", "Unknown")
            
            if status.lower() in ("succeeded", "ready"):
                print(f"  ✓ Analyzer ready! (took {elapsed}s)")
                return detail
            elif status.lower() == "failed":
                error_detail = detail.get("error", detail)
                raise Exception(f"Analyzer creation failed: {error_detail}")
            else:
                print(f"  Status: {status}... waiting ({elapsed}s)", end="\r")
                time.sleep(poll_interval)
                elapsed += poll_interval
        except Exception as e:
            if "failed" in str(e).lower():
                raise
            time.sleep(poll_interval)
            elapsed += poll_interval
    
    raise TimeoutError(f"Analyzer not ready after {max_wait} seconds")


def delete_analyzer_safe(client: AzureContentUnderstandingClient, analyzer_id: str):
    """Delete analyzer with error handling."""
    try:
        print(f"\nCleaning up analyzer: {analyzer_id}")
        client.delete_analyzer(analyzer_id)
        print(f"  ✓ Analyzer deleted")
    except Exception as e:
        print(f"  Warning: Failed to delete analyzer: {e}")


def cleanup_analyzer_set(client: AzureContentUnderstandingClient, analyzer_ids: List[str]):
    """Delete a set of analyzers in reverse creation order (classifier first, then inner)."""
    for analyzer_id in reversed(analyzer_ids):
        delete_analyzer_safe(client, analyzer_id)


def parse_inner_schema_args(inner_schema_args: Optional[List[str]]) -> Dict[str, Path]:
    """
    Parse --inner-schema arguments from 'alias=path' format.
    
    Args:
        inner_schema_args: List of strings like ['vehicle_title=schemas/title.json', ...]
    
    Returns:
        Dict mapping category alias to schema file Path
    
    Raises:
        ValueError: On invalid format, missing files, or duplicate aliases
    """
    if not inner_schema_args:
        return {}
    
    inner_schemas = {}
    for arg in inner_schema_args:
        if "=" not in arg:
            raise ValueError(
                f"Invalid --inner-schema format: '{arg}'\n"
                f"Expected format: alias=path (e.g., vehicle_title=schemas/title_v1.json)"
            )
        alias, path_str = arg.split("=", 1)
        alias = alias.strip()
        path = Path(path_str.strip())
        
        if not alias:
            raise ValueError(f"Empty alias in --inner-schema: '{arg}'")
        if alias in inner_schemas:
            raise ValueError(f"Duplicate --inner-schema alias: '{alias}'")
        if not path.exists():
            raise ValueError(f"Inner schema file not found: {path} (alias: {alias})")
        
        inner_schemas[alias] = path
    
    return inner_schemas


def validate_classify_route_mapping(
    classifier_schema: dict,
    inner_schemas: Dict[str, Path]
) -> List[str]:
    """
    Validate that inner schema mappings match classifier contentCategories.
    
    Returns list of category names that need inner analyzer IDs (have analyzerId placeholder).
    Raises ValueError on mapping mismatches.
    """
    content_categories = classifier_schema.get("config", {}).get("contentCategories", {})
    
    if not content_categories:
        raise ValueError("Classifier schema has no config.contentCategories")
    
    # Find categories that reference inner analyzers
    categories_needing_inner = {}
    categories_without_routing = []
    
    for cat_name, cat_def in content_categories.items():
        if "analyzerId" in cat_def:
            categories_needing_inner[cat_name] = cat_def["analyzerId"]
        else:
            categories_without_routing.append(cat_name)
    
    # Check for unresolved mappings: inner schemas provided but no matching category
    supplied_aliases = set(inner_schemas.keys())
    needed_aliases = set(categories_needing_inner.keys())
    
    unused = supplied_aliases - needed_aliases
    if unused:
        raise ValueError(
            f"Inner schemas supplied but no matching contentCategories: {unused}\n"
            f"Available categories with analyzerId: {sorted(needed_aliases)}\n"
            f"Categories without routing (no analyzerId needed): {sorted(categories_without_routing)}"
        )
    
    missing = needed_aliases - supplied_aliases
    if missing:
        raise ValueError(
            f"Classifier categories need inner schemas but none supplied: {missing}\n"
            f"Add --inner-schema flags for: " +
            " ".join(f"{m}=<path>" for m in sorted(missing))
        )
    
    return sorted(needed_aliases)


def patch_classifier_schema(
    classifier_schema: dict,
    category_to_analyzer_id: Dict[str, str]
) -> dict:
    """
    Replace placeholder analyzerId values in contentCategories with real IDs.
    Returns a deep copy with substitutions applied.
    """
    patched = copy.deepcopy(classifier_schema)
    categories = patched["config"]["contentCategories"]
    
    for cat_name, real_id in category_to_analyzer_id.items():
        old_id = categories[cat_name].get("analyzerId", "<none>")
        categories[cat_name]["analyzerId"] = real_id
        print(f"  Patched {cat_name}: {old_id} → {real_id}")
    
    return patched


def discover_schema_dir(dir_path: Path) -> Tuple[Dict[str, dict], Dict[str, Path]]:
    """
    Discover all analyzer schemas in a directory by reading their analyzerId fields.
    
    Returns:
        Tuple of (schemas_by_id, paths_by_id):
          - schemas_by_id: {analyzerId: parsed_schema_dict}
          - paths_by_id: {analyzerId: Path to schema file}
    
    Raises:
        ValueError on duplicate analyzerIds or schema-like files missing analyzerId.
    """
    dir_path = Path(dir_path)  # Accept both str and Path
    schemas_by_id = {}
    paths_by_id = {}
    
    for f in sorted(dir_path.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {f.name}: {e}")
        
        if not isinstance(data, dict):
            continue
        
        analyzer_id = data.get("analyzerId")
        if not analyzer_id:
            # Check if this looks like a schema (has baseAnalyzerId or fieldSchema)
            if data.get("baseAnalyzerId") or data.get("fieldSchema"):
                raise ValueError(
                    f"Schema file {f.name} has baseAnalyzerId or fieldSchema but no analyzerId. "
                    f"Add an analyzerId field to identify this schema."
                )
            continue  # Skip non-schema JSON files (README, metadata, etc.)
        
        if analyzer_id in schemas_by_id:
            raise ValueError(
                f"Duplicate analyzerId '{analyzer_id}' in:\n"
                f"  {paths_by_id[analyzer_id]}\n"
                f"  {f}"
            )
        
        schemas_by_id[analyzer_id] = data
        paths_by_id[analyzer_id] = f
    
    if not schemas_by_id:
        raise ValueError(f"No analyzer schemas found in {dir_path} (no .json files with analyzerId)")
    
    return schemas_by_id, paths_by_id


def build_schema_dag(schemas_by_id: Dict[str, dict]) -> Dict[str, List[str]]:
    """
    Build a dependency DAG from contentCategories.*.analyzerId references.
    
    Returns:
        Dict mapping analyzerId → list of local dependency analyzerIds.
        External refs (not in schemas_by_id) are excluded.
    """
    dag = {}
    for aid, schema in schemas_by_id.items():
        cats = schema.get("config", {}).get("contentCategories", {})
        deps = []
        for cat_def in cats.values():
            ref = cat_def.get("analyzerId")
            if ref and ref in schemas_by_id:
                deps.append(ref)
        dag[aid] = deps
    return dag


def topo_sort_schemas(dag: Dict[str, List[str]]) -> List[str]:
    """
    Topological sort of schema DAG. Returns leaf-first order (dependencies before dependents).
    
    Raises:
        ValueError on cycles.
    """
    # Kahn's algorithm
    in_degree = {node: 0 for node in dag}
    for node, deps in dag.items():
        for dep in deps:
            in_degree[dep] = in_degree.get(dep, 0) + 1
    
    # Wait — in_degree should count how many nodes depend ON each node.
    # Actually: dag[A] = [B, C] means A depends on B and C.
    # So B and C should be created before A.
    # in_degree[X] = number of nodes X depends on (reverse for topo sort)
    # Let me use the standard approach: reverse edges for Kahn's.
    
    # Reverse: edges from dependency → dependent
    in_degree = {node: 0 for node in dag}
    reverse_dag = {node: [] for node in dag}
    for node, deps in dag.items():
        for dep in deps:
            reverse_dag.setdefault(dep, []).append(node)
            in_degree[node] = in_degree.get(node, 0) + 1
    
    # Nodes with no dependencies go first (leaves)
    queue = [n for n in dag if in_degree.get(n, 0) == 0]
    result = []
    
    while queue:
        queue.sort()  # deterministic ordering
        node = queue.pop(0)
        result.append(node)
        for dependent in reverse_dag.get(node, []):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)
    
    if len(result) != len(dag):
        visited = set(result)
        cycle_nodes = [n for n in dag if n not in visited]
        raise ValueError(
            f"Circular dependency detected among schemas: {cycle_nodes}"
        )
    
    return result


def find_root_schemas(dag: Dict[str, List[str]]) -> List[str]:
    """Find root schemas (those not referenced as dependencies by other schemas)."""
    all_deps = set()
    for deps in dag.values():
        all_deps.update(deps)
    return [aid for aid in dag if aid not in all_deps]


def extract_token_usage(result: dict) -> Dict[str, Any]:
    """Extract token usage from a CU API result."""
    usage = result.get("usage", {})
    tokens = usage.get("tokens", {})
    input_tokens = sum(v for k, v in tokens.items() if "input" in k.lower())
    output_tokens = sum(v for k, v in tokens.items() if "output" in k.lower())
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "contextualization_tokens": usage.get("contextualizationTokens", 0),
        "document_pages": usage.get("documentPagesStandard", 0),
        "token_detail": tokens,
    }


def load_result_files(results_dir: Path) -> Dict[str, dict]:
    """Load all JSON result files from a directory, keyed by document name."""
    results = {}
    for f in sorted(results_dir.glob("*.json")):
        if f.name == "metadata.json" or f.name.endswith(".summary.json"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            doc_name = data.get("_metadata", {}).get("document", f.stem)
            results[doc_name] = data
        except (json.JSONDecodeError, KeyError):
            continue
    return results


def extract_confidence_map(result: dict) -> Dict[str, float]:
    """Extract field → confidence mapping from a CU result."""
    conf_map = {}
    result_data = result.get("result", {})
    
    def walk_fields(fields: dict, prefix: str = ""):
        for name, field in fields.items():
            full_name = f"{prefix}{name}" if prefix else name
            if isinstance(field, dict):
                if "confidence" in field:
                    conf_map[full_name] = field["confidence"]
                # Recurse into nested objects
                if "valueObject" in field:
                    walk_fields(field["valueObject"], f"{full_name}.")
                elif "properties" in field:
                    walk_fields(field["properties"], f"{full_name}.")
    
    # Handle both flat and contents-based results
    if "fields" in result_data:
        walk_fields(result_data["fields"])
    for content in result_data.get("contents", []):
        cat = content.get("category", "")
        prefix = f"{cat}." if cat else ""
        if "fields" in content:
            walk_fields(content["fields"], prefix)
    
    return conf_map


def extract_value_map(result: dict) -> Dict[str, Any]:
    """Extract field → value mapping from a CU result."""
    val_map = {}
    result_data = result.get("result", {})
    
    def walk_fields(fields: dict, prefix: str = ""):
        for name, field in fields.items():
            full_name = f"{prefix}{name}" if prefix else name
            if isinstance(field, dict):
                # Get the actual value
                for vkey in ("valueString", "valueNumber", "valueBoolean", "valueDate"):
                    if vkey in field:
                        val_map[full_name] = field[vkey]
                        break
                if "valueArray" in field:
                    val_map[full_name] = f"[{len(field['valueArray'])} items]"
                if "valueObject" in field:
                    walk_fields(field["valueObject"], f"{full_name}.")
    
    if "fields" in result_data:
        walk_fields(result_data["fields"])
    for content in result_data.get("contents", []):
        cat = content.get("category", "")
        prefix = f"{cat}." if cat else ""
        if "fields" in content:
            walk_fields(content["fields"], prefix)
    
    return val_map


def generate_comparison_report(
    current_results_dir: Path,
    previous_results_dir: Path,
    output_path: Path
):
    """Generate a markdown comparison report between two result sets."""
    current = load_result_files(current_results_dir)
    previous = load_result_files(previous_results_dir)
    
    if not previous:
        raise ValueError(f"No results found in {previous_results_dir}")
    
    # Match documents
    common_docs = sorted(set(current.keys()) & set(previous.keys()))
    only_current = sorted(set(current.keys()) - set(previous.keys()))
    only_previous = sorted(set(previous.keys()) - set(current.keys()))
    
    lines = [
        "# Comparison Report\n",
        f"**Current**: {current_results_dir}  ",
        f"**Previous**: {previous_results_dir}  ",
        f"**Documents matched**: {len(common_docs)} | "
        f"Only in current: {len(only_current)} | Only in previous: {len(only_previous)}\n",
    ]
    
    if not common_docs:
        # Try stem-based matching as fallback
        current_stems = {Path(k).stem: k for k in current}
        previous_stems = {Path(k).stem: k for k in previous}
        stem_matches = sorted(set(current_stems.keys()) & set(previous_stems.keys()))
        if stem_matches:
            lines.append(f"\n*No exact document name matches. Matched {len(stem_matches)} by filename stem.*\n")
            common_docs = [(current_stems[s], previous_stems[s]) for s in stem_matches]
        else:
            lines.append("\n⚠️ No matching documents found between result sets.\n")
            output_path.write_text("\n".join(lines), encoding="utf-8")
            return
    else:
        common_docs = [(d, d) for d in common_docs]
    
    # Per-document comparison
    all_conf_deltas = []
    all_value_changes = []
    
    for curr_key, prev_key in common_docs:
        curr_result = current[curr_key]
        prev_result = previous[prev_key]
        
        curr_conf = extract_confidence_map(curr_result)
        prev_conf = extract_confidence_map(prev_result)
        curr_vals = extract_value_map(curr_result)
        prev_vals = extract_value_map(prev_result)
        
        all_fields = sorted(set(curr_conf.keys()) | set(prev_conf.keys()))
        
        if all_fields:
            lines.append(f"\n## {curr_key}\n")
            lines.append("| Field | Prev Value | Curr Value | Prev Conf | Curr Conf | Δ Conf |")
            lines.append("|-------|-----------|-----------|-----------|-----------|--------|")
            
            for field in all_fields:
                pv = str(prev_vals.get(field, "—"))[:40]
                cv = str(curr_vals.get(field, "—"))[:40]
                pc = prev_conf.get(field)
                cc = curr_conf.get(field)
                
                pc_str = f"{pc:.3f}" if pc is not None else "—"
                cc_str = f"{cc:.3f}" if cc is not None else "—"
                
                if pc is not None and cc is not None:
                    delta = cc - pc
                    delta_str = f"{delta:+.3f}"
                    if delta > 0.05:
                        delta_str = f"✅ {delta_str}"
                    elif delta < -0.05:
                        delta_str = f"⚠️ {delta_str}"
                    all_conf_deltas.append(delta)
                else:
                    delta_str = "—"
                
                changed = "🔄" if pv != cv else ""
                if pv != cv:
                    all_value_changes.append(field)
                
                lines.append(f"| {field} {changed} | {pv} | {cv} | {pc_str} | {cc_str} | {delta_str} |")
    
    # Summary
    lines.insert(4, "")
    lines.insert(5, "## Summary\n")
    if all_conf_deltas:
        avg_delta = sum(all_conf_deltas) / len(all_conf_deltas)
        improved = sum(1 for d in all_conf_deltas if d > 0.01)
        degraded = sum(1 for d in all_conf_deltas if d < -0.01)
        lines.insert(6, f"- **Avg confidence Δ**: {avg_delta:+.3f}")
        lines.insert(7, f"- **Fields improved**: {improved} | **Degraded**: {degraded} | **Stable**: {len(all_conf_deltas) - improved - degraded}")
        lines.insert(8, f"- **Value changes**: {len(all_value_changes)}")
    else:
        lines.insert(6, "- No comparable confidence data found.")
    
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Compared {len(common_docs)} document(s), {len(all_conf_deltas)} field comparisons")


def process_single_document(
    client: AzureContentUnderstandingClient,
    file_path: Path,
    file_idx: int,
    total_files: int,
    iteration: int,
    total_iterations: int,
    analyzer_id: str,
    run_id: str,
    results_dir: Path,
    timeout: int
) -> Tuple[bool, Dict[str, Any]]:
    """
    Process a single document (used for parallel processing).
    Returns (success, result_dict)
    """
    try:
        start_time = time.time()
        
        result = run_analysis(client, analyzer_id, file_path, timeout)
        
        result_path = save_result(
            result, results_dir, file_path.name,
            iteration, run_id, analyzer_id
        )
        
        elapsed = time.time() - start_time
        
        token_usage = extract_token_usage(result)
        
        return True, {
            "document": file_path.name,
            "iteration": iteration,
            "status": "success",
            "elapsed_seconds": elapsed,
            "result_file": result_path.name,
            "file_idx": file_idx,
            **token_usage,
        }
        
    except Exception as e:
        return False, {
            "document": file_path.name,
            "iteration": iteration,
            "status": "failed",
            "error": str(e),
            "file_idx": file_idx
        }


def main():
    parser = argparse.ArgumentParser(
        description="Create analyzer from schema and run test analysis"
    )
    parser.add_argument(
        "--schema", "-s",
        type=str,
        required=True,
        help="Path to analyzer schema JSON file"
    )
    parser.add_argument(
        "--analyzer-id",
        type=str,
        help="Custom analyzer ID (auto-generated if not provided)"
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="Input file or directory"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        required=True,
        help="Output directory for results"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of iterations per document (for stability testing)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Analysis timeout in seconds"
    )
    parser.add_argument(
        "--keep-analyzer",
        action="store_true",
        help="Keep analyzer after testing (don't delete)"
    )
    parser.add_argument(
        "--api-version",
        type=str,
        help=(
            "CU API version (default: CU_API_VERSION or 2025-11-01). "
            "Use 2026-06-01-preview for agentic preview analyzers."
        )
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Number of parallel workers for processing documents (default: 1, recommended: 3-5)"
    )
    parser.add_argument(
        "--inner-schema",
        action="append",
        metavar="ALIAS=PATH",
        help="Inner analyzer schema for classify-and-route (repeatable). "
             "Format: category_name=path/to/schema.json. "
             "Example: --inner-schema vehicle_title=schemas/title_v1.json"
    )
    parser.add_argument(
        "--schema-dir",
        type=str,
        help="Directory containing multiple analyzer schemas (alternative to --inner-schema). "
             "Auto-discovers schemas by reading analyzerId fields and resolves dependencies. "
             "All schemas are created in topological order (leaves first)."
    )
    parser.add_argument(
        "--root",
        type=str,
        help="Root analyzer ID when --schema-dir has multiple root schemas (those not "
             "referenced by any other schema). Required only if ambiguous."
    )
    parser.add_argument(
        "--compare-with",
        type=str,
        metavar="PREV_RESULTS_DIR",
        help="Compare results with a previous run directory. "
             "Produces a comparison.md report with per-field deltas."
    )
    
    args = parser.parse_args()
    load_dotenv()
    args.api_version = resolve_api_version(args.api_version)
    
    # Validate mutually exclusive args
    if args.schema_dir and args.inner_schema:
        print("❌ --schema-dir and --inner-schema are mutually exclusive.")
        print("   Use --schema-dir for auto-discovery or --inner-schema for explicit mapping.")
        sys.exit(1)
    
    # --- Schema-dir mode: discover and set up schemas from directory ---
    schema_dir_mode = False
    schema_dir_schemas = {}  # analyzerId → schema dict
    schema_dir_paths = {}    # analyzerId → Path
    schema_dir_order = []    # topological order (leaf-first)
    
    if args.schema_dir:
        schema_dir_path = Path(args.schema_dir)
        if not schema_dir_path.is_dir():
            print(f"Error: --schema-dir path is not a directory: {schema_dir_path}")
            sys.exit(1)
        
        schema_dir_mode = True
        
        print(f"\n{'='*60}")
        print(f"Step 1: Discover Schemas in {schema_dir_path}")
        print(f"{'='*60}")
        
        try:
            schema_dir_schemas, schema_dir_paths = discover_schema_dir(schema_dir_path)
        except ValueError as e:
            print(f"\n❌ {e}")
            sys.exit(1)
        
        print(f"  Found {len(schema_dir_schemas)} analyzer schema(s):")
        for aid, p in schema_dir_paths.items():
            schema = schema_dir_schemas[aid]
            has_cats = bool(schema.get("config", {}).get("contentCategories", {}))
            label = "classifier" if has_cats else "extractor"
            print(f"    {aid} ({label}) ← {p.name}")
        
        # Build DAG and sort
        dag = build_schema_dag(schema_dir_schemas)
        try:
            schema_dir_order = topo_sort_schemas(dag)
        except ValueError as e:
            print(f"\n❌ {e}")
            sys.exit(1)
        
        print(f"\n  Creation order: {' → '.join(schema_dir_order)}")
        
        # Determine root (the analyzer to test against)
        roots = find_root_schemas(dag)
        if len(roots) == 0:
            print("\n❌ No root schemas found (all schemas are referenced by others).")
            sys.exit(1)
        elif len(roots) == 1:
            root_id = roots[0]
        elif args.root:
            if args.root not in schema_dir_schemas:
                print(f"\n❌ --root '{args.root}' not found. Available: {sorted(schema_dir_schemas.keys())}")
                sys.exit(1)
            root_id = args.root
        else:
            print(f"\n❌ Multiple root schemas found: {roots}")
            print(f"   Use --root to specify which analyzer to test against.")
            sys.exit(1)
        
        print(f"  Root analyzer (test target): {root_id}")
        
        # Validate all schemas
        print(f"\n{'='*60}")
        print(f"Validating All Schemas")
        print(f"{'='*60}")
        for aid in schema_dir_order:
            p = schema_dir_paths[aid]
            if not validate_schema(p, strict=False, api_version=args.api_version):
                print(f"\n❌ Schema validation failed for '{aid}': {p}")
                sys.exit(1)
        
        # Set up variables for the existing flow
        schema = schema_dir_schemas[root_id]
        schema_path = schema_dir_paths[root_id]
        analyzer_id = root_id
        content_categories = schema.get("config", {}).get("contentCategories", {})
        is_classify_route = bool(content_categories)
        inner_schemas = {}  # Not used in schema-dir mode
        num_fields = 0 if is_classify_route else len(schema.get("fieldSchema", {}).get("fields", {}))
    else:
        # --- Standard mode: single schema file ---
        # Validate schema path
        schema_path = Path(args.schema)
        if not schema_path.exists():
            print(f"Error: Schema file not found: {schema_path}")
            sys.exit(1)
        
        # Validate schema FIRST (before loading or creating analyzer)
        print(f"\n{'='*60}")
        print(f"Step 1: Validate Schema")
        print(f"{'='*60}")
        if not validate_schema(schema_path, strict=False, api_version=args.api_version):
            print("\n❌ Schema validation failed. Please fix errors and try again.")
            sys.exit(1)
        
        # Load schema
        print(f"\n{'='*60}")
        print(f"Step 2: Load Schema")
        print(f"{'='*60}")
        schema = load_schema(schema_path)
        print(f"  Schema description: {schema.get('description', 'N/A')}")
        
        # Detect schema type: field extraction vs classify-and-route
        content_categories = schema.get("config", {}).get("contentCategories", {})
        is_classify_route = bool(content_categories)
        
        # Parse and validate inner schema mappings for classify-and-route
        inner_schemas = {}
        if args.inner_schema:
            try:
                inner_schemas = parse_inner_schema_args(args.inner_schema)
            except ValueError as e:
                print(f"\n❌ {e}")
                sys.exit(1)
        
        if is_classify_route:
            print(f"  Schema type: Classify-and-Route ({len(content_categories)} categories)")
            for cat_name, cat_def in content_categories.items():
                analyzer_ref = cat_def.get("analyzerId", "(classification only)")
                inner_ref = f" ← {inner_schemas[cat_name]}" if cat_name in inner_schemas else ""
                print(f"    - {cat_name} → {analyzer_ref}{inner_ref}")
            
            # Validate mappings
            try:
                categories_with_inner = validate_classify_route_mapping(schema, inner_schemas)
            except ValueError as e:
                print(f"\n❌ {e}")
                sys.exit(1)
            
            # Validate each inner schema
            if inner_schemas:
                print(f"\n{'='*60}")
                print(f"Validating Inner Schemas")
                print(f"{'='*60}")
                for alias, inner_path in inner_schemas.items():
                    if not validate_schema(inner_path, strict=False, api_version=args.api_version):
                        print(f"\n❌ Inner schema validation failed for '{alias}': {inner_path}")
                        sys.exit(1)
            
            num_fields = 0
        elif args.inner_schema:
            print("\n❌ --inner-schema provided but schema has no contentCategories.")
            print("   --inner-schema is only used with classify-and-route classifier schemas.")
            sys.exit(1)
        else:
            num_fields = len(schema.get("fieldSchema", {}).get("fields", {}))
            print(f"  Schema type: Field Extraction ({num_fields} fields)")
        
        # Generate or use provided analyzer ID
        if args.analyzer_id:
            analyzer_id = args.analyzer_id
        else:
            analyzer_id = generate_analyzer_id(schema_path)
    
    # --- Common: validate input/output paths ---
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input path not found: {input_path}")
        sys.exit(1)
    
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"  Analyzer ID: {analyzer_id}")
    
    # Get files to process
    files = get_supported_files(input_path)
    if not files:
        print(f"Error: No supported documents found in {input_path}")
        sys.exit(1)
    
    # Check for protected PDFs and filter them out
    processable_files, protected_files = check_files_for_protection(files)
    
    if protected_files:
        print(f"\n⚠️  Found {len(protected_files)} protected/encrypted PDF(s) - these will be skipped:")
        for pf, reason in protected_files:
            print(f"   - {pf.name}: {reason}")
    
    if not processable_files:
        print(f"\nError: All {len(files)} document(s) are protected or unreadable. Cannot proceed.")
        sys.exit(1)
    
    files = processable_files  # Use only processable files from here on
    
    print(f"\nFound {len(files)} processable document(s) ({len(protected_files)} skipped)")
    for f in files:
        print(f"  - {f.name}")
    
    # Create client
    print(f"\n{'='*60}")
    print(f"Step 3: Connect to Azure AI")
    print(f"{'='*60}")
    print(f"Connecting to Azure AI Content Understanding...")
    client = get_client(api_version=args.api_version)
    print(f"  ✓ Connected")
    
    # Generate run ID
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{analyzer_id[:8]}"
    
    # Track all created analyzers for cleanup
    created_analyzer_ids = []
    category_to_real_id = {}
    
    try:
        # --- Schema-dir mode: create all schemas in topological order ---
        if schema_dir_mode:
            print(f"\n{'='*60}")
            print(f"Step 4: Create Analyzers ({len(schema_dir_order)} schemas)")
            print(f"{'='*60}")
            
            for i, aid in enumerate(schema_dir_order, 1):
                s = schema_dir_schemas[aid]
                p = schema_dir_paths[aid]
                has_cats = bool(s.get("config", {}).get("contentCategories", {}))
                label = "classifier" if has_cats else "extractor"
                
                print(f"\n  [{i}/{len(schema_dir_order)}] Creating {label}: {aid}")
                print(f"    Schema: {p.name}")
                
                try:
                    create_analyzer(client, aid, s)
                    created_analyzer_ids.append(aid)
                except Exception as e:
                    print(f"\n❌ Failed to create analyzer '{aid}': {e}")
                    raise
        
        # --- Standard --inner-schema mode: create inner analyzers first ---
        elif is_classify_route and inner_schemas:
            print(f"\n{'='*60}")
            print(f"Step 4a: Create Inner Analyzers ({len(inner_schemas)})")
            print(f"{'='*60}")
            
            category_to_real_id = {}
            for alias, inner_path in inner_schemas.items():
                inner_schema = load_schema(inner_path)
                inner_id = generate_analyzer_id(inner_path)
                
                print(f"\n📋 Creating inner analyzer for '{alias}': {inner_id}")
                print(f"   Schema: {inner_path}")
                
                try:
                    create_analyzer(client, inner_id, inner_schema)
                    created_analyzer_ids.append(inner_id)
                    category_to_real_id[alias] = inner_id
                except Exception as e:
                    print(f"\n❌ Failed to create inner analyzer '{alias}': {e}")
                    raise
            
            # Patch classifier schema with real inner analyzer IDs
            print(f"\n{'='*60}")
            print(f"Step 4b: Patch Classifier Schema")
            print(f"{'='*60}")
            schema = patch_classifier_schema(schema, category_to_real_id)
            
            # Validate the patched classifier schema
            print(f"\n  Validating patched classifier schema...")
        
        # Create the main analyzer (field extraction or patched classifier)
        # Skip if schema-dir mode — all analyzers already created above
        if not schema_dir_mode:
            print(f"\n{'='*60}")
            step_label = "Step 4c" if is_classify_route and inner_schemas else "Step 4"
            print(f"{step_label}: Create {'Classifier' if is_classify_route else 'Analyzer'}")
            print(f"{'='*60}")
            create_analyzer(client, analyzer_id, schema)
            created_analyzer_ids.append(analyzer_id)
        
        # Run analysis
        print(f"\n{'='*60}")
        print(f"Step 5: Run Analysis on {len(files)} document(s)")
        print(f"{'='*60}")
        print(f"Iterations per document: {args.iterations}")
        print(f"Output: {output_path}")
        if is_classify_route:
            print(f"Mode: Classify-and-Route (results include category + routed fields)")
        print("-" * 60)
        
        # Create metadata
        test_type = "classify_route" if is_classify_route else (
            "stability" if args.iterations > 1 else "batch" if len(files) > 1 else "single"
        )
        metadata = create_run_metadata(
            run_id=run_id,
            analyzer_id=analyzer_id,
            input_path=str(input_path),
            documents=[f.name for f in files],
            iterations=args.iterations,
            test_type=test_type,
            api_version=args.api_version,
        )
        metadata["schema_file"] = str(schema_path)
        metadata["analyzer_created"] = True
        metadata["all_analyzer_ids"] = list(created_analyzer_ids)
        
        if schema_dir_mode:
            metadata["schema_dir"] = {
                "directory": str(schema_dir_path),
                "creation_order": schema_dir_order,
                "root_analyzer": root_id,
                "schemas": {
                    aid: str(schema_dir_paths[aid])
                    for aid in schema_dir_order
                }
            }
        elif is_classify_route and inner_schemas:
            metadata["classify_route"] = {
                "classifier_id": analyzer_id,
                "inner_analyzers": {
                    alias: {"schema": str(path), "analyzer_id": category_to_real_id[alias]}
                    for alias, path in inner_schemas.items()
                },
                "categories": {
                    cat_name: {
                        "has_routing": "analyzerId" in cat_def,
                        "analyzer_id": category_to_real_id.get(cat_name)
                    }
                    for cat_name, cat_def in content_categories.items()
                }
            }
        
        # Add protected files info to metadata
        if protected_files:
            metadata["skipped_protected_files"] = [
                {"file": pf.name, "reason": reason} for pf, reason in protected_files
            ]
        
        # Save initial metadata
        metadata_path = output_path / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        # Process files
        results_dir = output_path
        successful = 0
        failed = 0
        results_summary = []
        
        # Create list of all tasks (document + iteration combinations)
        tasks = []
        for file_idx, file_path in enumerate(files, 1):
            for iteration in range(1, args.iterations + 1):
                tasks.append((file_path, file_idx, iteration))
        
        total_tasks = len(tasks)
        print(f"Processing {total_tasks} task(s) with {args.max_workers} worker(s)...")
        
        if args.max_workers == 1:
            # Sequential processing (original behavior)
            for file_idx, file_path in enumerate(files, 1):
                print(f"\n[{file_idx}/{len(files)}] Processing: {file_path.name}")
                
                for iteration in range(1, args.iterations + 1):
                    iter_label = f" (iteration {iteration}/{args.iterations})" if args.iterations > 1 else ""
                    
                    print(f"  Running analysis{iter_label}...", end=" ", flush=True)
                    
                    success, result_dict = process_single_document(
                        client, file_path, file_idx, len(files),
                        iteration, args.iterations, analyzer_id, run_id,
                        results_dir, args.timeout
                    )
                    
                    if success:
                        print(f"✓ Done ({result_dict['elapsed_seconds']:.1f}s) - Saved: {result_dict['result_file']}")
                        successful += 1
                    else:
                        print(f"✗ Error: {result_dict['error']}")
                        failed += 1
                    
                    results_summary.append(result_dict)
        else:
            # Parallel processing
            print()  # Blank line before parallel output
            with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
                # Submit all tasks
                futures = {
                    executor.submit(
                        process_single_document,
                        client, file_path, file_idx, len(files),
                        iteration, args.iterations, analyzer_id, run_id,
                        results_dir, args.timeout
                    ): (file_path, file_idx, iteration)
                    for file_path, file_idx, iteration in tasks
                }
                
                # Process completed tasks
                completed = 0
                for future in as_completed(futures):
                    file_path, file_idx, iteration = futures[future]
                    completed += 1
                    
                    try:
                        success, result_dict = future.result()
                        
                        if success:
                            print(f"✅ [{completed}/{total_tasks}] {file_path.name} - {result_dict['elapsed_seconds']:.1f}s - {result_dict['result_file']}")
                            successful += 1
                        else:
                            print(f"❌ [{completed}/{total_tasks}] {file_path.name} - Error: {result_dict['error']}")
                            failed += 1
                        
                        results_summary.append(result_dict)
                        
                    except Exception as e:
                        print(f"❌ [{completed}/{total_tasks}] {file_path.name} - Exception: {e}")
                        failed += 1
                        results_summary.append({
                            "document": file_path.name,
                            "iteration": iteration,
                            "status": "failed",
                            "error": str(e),
                            "file_idx": file_idx
                        })
        
        # Update metadata with results
        metadata["completed_at"] = datetime.utcnow().isoformat() + "Z"
        metadata["successful"] = successful
        metadata["failed"] = failed
        metadata["results"] = results_summary
        metadata["analyzer_kept"] = args.keep_analyzer
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"COMPLETED: {successful} successful, {failed} failed")
        print(f"Results saved to: {output_path}")
        print(f"Metadata: {metadata_path}")
        if is_classify_route and category_to_real_id:
            print(f"Classifier ID: {analyzer_id}")
            for alias, real_id in category_to_real_id.items():
                print(f"  Inner analyzer ({alias}): {real_id}")
        elif schema_dir_mode:
            print(f"Root analyzer: {analyzer_id}")
            print(f"  All analyzers: {', '.join(schema_dir_order)}")
        elif is_classify_route:
            print(f"Classifier ID: {analyzer_id} (classify-only, no inner analyzers)")
        else:
            print(f"Analyzer ID: {analyzer_id}")
        
        # Token usage summary
        success_results = [r for r in results_summary if r.get("status") == "success"]
        total_input = sum(r.get("input_tokens", 0) for r in success_results)
        total_output = sum(r.get("output_tokens", 0) for r in success_results)
        total_context = sum(r.get("contextualization_tokens", 0) for r in success_results)
        total_pages = sum(r.get("document_pages", 0) for r in success_results)
        
        if total_input > 0 or total_output > 0:
            print(f"\n--- Token Usage ---")
            print(f"  Input tokens:  {total_input:,}")
            print(f"  Output tokens: {total_output:,}")
            if total_context > 0:
                print(f"  Context tokens: {total_context:,}")
            print(f"  Total tokens:  {total_input + total_output:,}")
            if total_pages > 0:
                print(f"  Document pages: {total_pages}")
            if len(success_results) > 1:
                avg_input = total_input / len(success_results)
                avg_output = total_output / len(success_results)
                print(f"  Avg per document: {avg_input:,.0f} in / {avg_output:,.0f} out")
            
            # Collect per-model breakdown
            all_detail = {}
            for r in success_results:
                for k, v in r.get("token_detail", {}).items():
                    all_detail[k] = all_detail.get(k, 0) + v
            if all_detail:
                print(f"  Model breakdown:")
                for k in sorted(all_detail.keys()):
                    print(f"    {k}: {all_detail[k]:,}")
        
        # Add token summary to metadata
        metadata["token_summary"] = {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_contextualization_tokens": total_context,
            "total_document_pages": total_pages,
            "per_model": all_detail if total_input > 0 else {},
        }
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        # --compare-with: generate comparison report
        if args.compare_with:
            compare_path = Path(args.compare_with)
            if not compare_path.exists():
                print(f"\n⚠️  --compare-with path not found: {compare_path}")
            else:
                print(f"\n{'='*60}")
                print(f"Comparison with: {compare_path}")
                print(f"{'='*60}")
                try:
                    generate_comparison_report(
                        current_results_dir=output_path,
                        previous_results_dir=compare_path,
                        output_path=output_path / "comparison.md"
                    )
                    print(f"  ✓ Comparison report: {output_path / 'comparison.md'}")
                except Exception as e:
                    print(f"  ⚠️  Comparison failed: {e}")
        
        if failed > 0:
            return_code = 1
        else:
            return_code = 0
        
    finally:
        # Clean up all analyzers unless --keep-analyzer specified
        if not args.keep_analyzer and created_analyzer_ids:
            cleanup_analyzer_set(client, created_analyzer_ids)
        elif args.keep_analyzer and created_analyzer_ids:
            print(f"\n✓ All analyzers kept ({len(created_analyzer_ids)} total):")
            for aid in created_analyzer_ids:
                print(f"    {aid}")
            print(f"  To use classifier: python run.py --analyzer-id {analyzer_id} ...")
            print(f"  To delete all: " + " && ".join(
                f"python run.py --delete-analyzer {aid}" for aid in reversed(created_analyzer_ids)
            ))
    
    sys.exit(return_code)


if __name__ == "__main__":
    main()
