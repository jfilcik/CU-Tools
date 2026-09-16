"""Offline tests write only beneath this subtree and never connect to services."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

MIGRATION_ROOT = str(Path(__file__).resolve().parents[1])
if MIGRATION_ROOT not in sys.path:
    sys.path.insert(0, MIGRATION_ROOT)


@pytest.fixture(autouse=True)
def no_service_calls(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Offline migration must not open network connections or launch commands")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)


@pytest.fixture
def workspace():
    root = Path(__file__).resolve().parent / ".test-work"
    path = root / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path)
        try:
            root.rmdir()
        except OSError:
            pass


@pytest.fixture
def export_file(workspace):
    def write(value, name="export.json"):
        path = workspace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    return write


@pytest.fixture
def definition():
    return {
        "analyzerId": "invoice_preview",
        "scenario": "document",
        "description": "Synthetic invoice test schema",
        "fieldSchema": {"fields": {"Total": {"type": "number", "method": "extract"}}},
        "config": {"returnDetails": True},
    }
