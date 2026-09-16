"""Regression guard for the public, official-CLI-only CU execution boundary."""

import ast
from pathlib import Path
import re
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
RETIRED = (
    "cu-analyzer-run", "cu-client", "cu-cli", "cu-prompt-cache", "tpm-manager",
)
FORBIDDEN_IMPORTS = (
    "cu_cli", "cu_cli_core", "content_understanding_client",
    "azure.ai.contentunderstanding", "azure.kusto",
)
CU_HTTP_PATTERN = re.compile(r"/contentunderstanding/|/contentunderstanding\?")
SIGNED_URL = re.compile(r"https?://[^\s\"'<>]+[?&]sig=[A-Za-z0-9%+/=]{16,}", re.IGNORECASE)


def source_files():
    paths = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--",
         "*.py", "*.md", "*.http", "*.json", "*.js", "*.html", "*.sample"],
        cwd=ROOT, check=True, capture_output=True, text=True,
        encoding="utf-8", stdin=subprocess.DEVNULL,
    ).stdout.split("\0")
    for name in sorted(set(paths)):
        path = ROOT / name
        if path.is_file():
            yield path


@pytest.mark.parametrize("name", RETIRED)
def test_retired_tools_are_absent(name):
    assert not (ROOT / "tools" / name).exists()


def test_no_cu_sdk_internal_cli_or_kusto_imports():
    violations = []
    for path in source_files():
        if path.suffix != ".py" or "tests" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                if any(name == blocked or name.startswith(blocked + ".") for blocked in FORBIDDEN_IMPORTS):
                    violations.append(f"{path.relative_to(ROOT)}:{node.lineno}: {name}")
    assert not violations, "\n".join(violations)


def test_no_direct_cu_http_routes_in_executable_python():
    violations = []
    for path in source_files():
        if path.suffix != ".py" or "tests" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if CU_HTTP_PATTERN.search(node.value):
                    violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not violations, "Direct CU route strings: " + ", ".join(violations)


def test_offline_validator_has_only_standard_library_imports():
    import sys

    path = ROOT / "tools" / "cu-analyzer-validate" / "cu_analyzer_validator.py"
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            assert name.partition(".")[0] in sys.stdlib_module_names, name
            assert name.partition(".")[0] not in {"socket", "urllib", "http", "subprocess"}, name


def test_no_signed_sample_urls_or_internal_diagnostic_headers():
    violations = []
    for path in source_files():
        if "tests" in path.parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if SIGNED_URL.search(line) or "x-ms-diagnostics" in line.lower():
                violations.append(f"{path.relative_to(ROOT)}:{number}")
    assert not violations, "Restricted references (values withheld): " + ", ".join(violations)
