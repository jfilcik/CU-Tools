"""
cu_cli.cli - Command-line entry point for cu-cli.

Usage:
    python -m cu_cli validate-setup [--verbose]
    python -m cu_cli analyzer list
    python -m cu_cli analyzer get --analyzer-id my-analyzer
    python -m cu_cli analyzer create --analyzer-id my-analyzer --schema schema.json [--no-replace]
    python -m cu_cli analyzer delete --analyzer-id my-analyzer
    python -m cu_cli analyze file --analyzer-id my-analyzer --input doc.pdf [--output result.json]
    python -m cu_cli analyze url --analyzer-id my-analyzer --url https://... [--output result.json]
    python -m cu_cli classifier create --classifier-id my-classifier --schema schema.json
    python -m cu_cli classify --classifier-id my-classifier --input doc.pdf [--output result.json]
    python -m cu_cli defaults get
    python -m cu_cli defaults set --model gpt-4.1=my-deployment [--model gpt-4o=other-deployment]

All commands print JSON to stdout (or to --output if provided) and exit
non-zero on failure, so cu-cli can be used both interactively and from
scripts/CI.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional

from . import operations as ops


def _print_json(data, output: Optional[str] = None) -> None:
    text = json.dumps(data, indent=2, default=str)
    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"Wrote {output}")
    else:
        print(text)


def _load_schema(schema_path: str) -> dict:
    path = Path(schema_path)
    if not path.exists():
        raise ops.CUCliError(f"Schema file not found: {schema_path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_model_deployment_args(model_args) -> Dict[str, Optional[str]]:
    """Parse repeated --model name=deployment (or name= to clear) args."""
    result: Dict[str, Optional[str]] = {}
    for entry in model_args or []:
        if "=" not in entry:
            raise ops.CUCliError(
                f"--model must be in the form name=deployment (got: {entry!r})"
            )
        name, _, deployment = entry.partition("=")
        result[name.strip()] = deployment.strip() or None
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cu-cli",
        description="Run operations against the Azure AI Content Understanding service.",
    )
    parser.add_argument("--api-version", help="Override CU API version")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate-setup", help="Validate connectivity/auth")
    p_validate.add_argument("--verbose", action="store_true")

    p_analyzer = sub.add_parser("analyzer", help="Analyzer operations")
    analyzer_sub = p_analyzer.add_subparsers(dest="analyzer_command", required=True)

    analyzer_sub.add_parser("list", help="List all analyzers")

    p_get = analyzer_sub.add_parser("get", help="Get analyzer detail")
    p_get.add_argument("--analyzer-id", required=True)

    p_create = analyzer_sub.add_parser("create", help="Create analyzer and wait until ready")
    p_create.add_argument("--analyzer-id", required=True)
    p_create.add_argument("--schema", required=True, help="Path to schema JSON file")
    p_create.add_argument("--max-wait", type=int, default=ops.DEFAULT_CREATE_MAX_WAIT_SECONDS)
    p_create.add_argument(
        "--no-replace",
        action="store_true",
        help="Do not delete an existing analyzer with the same ID first",
    )

    p_delete = analyzer_sub.add_parser("delete", help="Delete an analyzer")
    p_delete.add_argument("--analyzer-id", required=True)

    p_analyze = sub.add_parser("analyze", help="Run analysis")
    analyze_sub = p_analyze.add_subparsers(dest="analyze_command", required=True)

    p_analyze_file = analyze_sub.add_parser("file", help="Analyze a local file")
    p_analyze_file.add_argument("--analyzer-id", required=True)
    p_analyze_file.add_argument("--input", required=True, help="Path to local file")
    p_analyze_file.add_argument("--timeout", type=int, default=ops.DEFAULT_ANALYZE_TIMEOUT_SECONDS)
    p_analyze_file.add_argument("--diagnostics", action="store_true")

    p_analyze_url = analyze_sub.add_parser("url", help="Analyze a document URL")
    p_analyze_url.add_argument("--analyzer-id", required=True)
    p_analyze_url.add_argument("--url", required=True)
    p_analyze_url.add_argument("--timeout", type=int, default=ops.DEFAULT_ANALYZE_TIMEOUT_SECONDS)
    p_analyze_url.add_argument("--diagnostics", action="store_true")

    p_classifier = sub.add_parser("classifier", help="Classifier operations")
    classifier_sub = p_classifier.add_subparsers(dest="classifier_command", required=True)
    p_classifier_create = classifier_sub.add_parser("create", help="Create classifier and wait until ready")
    p_classifier_create.add_argument("--classifier-id", required=True)
    p_classifier_create.add_argument("--schema", required=True)
    p_classifier_create.add_argument("--max-wait", type=int, default=ops.DEFAULT_CREATE_MAX_WAIT_SECONDS)

    p_classify = sub.add_parser("classify", help="Classify a file or URL")
    p_classify.add_argument("--classifier-id", required=True)
    p_classify.add_argument("--input", required=True, help="Local file path or URL")
    p_classify.add_argument("--timeout", type=int, default=ops.DEFAULT_ANALYZE_TIMEOUT_SECONDS)

    p_defaults = sub.add_parser("defaults", help="Model deployment defaults")
    defaults_sub = p_defaults.add_subparsers(dest="defaults_command", required=True)
    defaults_sub.add_parser("get", help="Get current defaults")
    p_defaults_set = defaults_sub.add_parser("set", help="Update model deployment defaults")
    p_defaults_set.add_argument(
        "--model",
        action="append",
        help="name=deployment (repeatable); name= clears the mapping",
    )

    for p in (
        p_get, p_create, p_delete, p_analyze_file, p_analyze_url,
        p_classifier_create, p_classify, p_validate,
    ):
        p.add_argument("--output", help="Write JSON result to this file instead of stdout")
    p_defaults.add_argument("--output", help="Write JSON result to this file instead of stdout")

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        client = ops.get_client(api_version=args.api_version)

        if args.command == "validate-setup":
            result = ops.validate_setup(client, verbose=args.verbose)
        elif args.command == "analyzer":
            if args.analyzer_command == "list":
                result = ops.list_analyzers(client)
            elif args.analyzer_command == "get":
                result = ops.get_analyzer(client, args.analyzer_id)
            elif args.analyzer_command == "create":
                schema = _load_schema(args.schema)
                result = ops.create_analyzer_and_wait(
                    client,
                    args.analyzer_id,
                    schema,
                    max_wait=args.max_wait,
                    replace_existing=not args.no_replace,
                    on_progress=lambda status, elapsed: print(
                        f"  status={status} elapsed={elapsed}s", file=sys.stderr
                    ),
                )
            elif args.analyzer_command == "delete":
                ops.delete_analyzer(client, args.analyzer_id)
                result = {"deleted": args.analyzer_id}
            else:  # pragma: no cover - argparse enforces valid subcommands
                raise ops.CUCliError(f"Unknown analyzer command: {args.analyzer_command}")
        elif args.command == "analyze":
            if args.analyze_command == "file":
                result = ops.analyze_file_and_wait(
                    client, args.analyzer_id, Path(args.input),
                    timeout=args.timeout, diagnostics=args.diagnostics,
                )
            elif args.analyze_command == "url":
                result = ops.analyze_url_and_wait(
                    client, args.analyzer_id, args.url,
                    timeout=args.timeout, diagnostics=args.diagnostics,
                )
            else:  # pragma: no cover
                raise ops.CUCliError(f"Unknown analyze command: {args.analyze_command}")
        elif args.command == "classifier":
            schema = _load_schema(args.schema)
            result = ops.create_classifier_and_wait(
                client, args.classifier_id, schema, max_wait=args.max_wait,
            )
        elif args.command == "classify":
            result = ops.classify_and_wait(
                client, args.classifier_id, args.input, timeout=args.timeout,
            )
        elif args.command == "defaults":
            if args.defaults_command == "get":
                result = ops.get_defaults(client)
            elif args.defaults_command == "set":
                model_deployments = _parse_model_deployment_args(args.model)
                result = ops.update_defaults(client, model_deployments)
            else:  # pragma: no cover
                raise ops.CUCliError(f"Unknown defaults command: {args.defaults_command}")
        else:  # pragma: no cover - argparse enforces valid subcommands
            raise ops.CUCliError(f"Unknown command: {args.command}")

        _print_json(result, getattr(args, "output", None))
        return 0

    except ops.CUCliError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 - surface any HTTP/other error to the caller
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
