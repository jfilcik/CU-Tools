"""Focused tests for the obligation golden-set comparison."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evaluate = load_module("golden_evaluate", PROJECT_DIR / "evaluation" / "evaluate.py")
prepare = load_module(
    "golden_prepare",
    PROJECT_DIR / "scripts" / "prepare_dataset.py",
)
build_schemas = load_module(
    "golden_schemas",
    PROJECT_DIR / "scripts" / "build_schemas.py",
)


def test_selection_manifest_and_materialized_contracts_are_stable() -> None:
    manifest = json.loads(
        (PROJECT_DIR / "dataset" / "selection_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(manifest["documents"]) == 10
    assert len({doc["doc_id"] for doc in manifest["documents"]}) == 10
    assert all(doc["expected_words"] <= 1000 for doc in manifest["documents"])

    materialized = prepare.prepare_dataset(
        prepare.DEFAULT_SOURCE,
        prepare.DEFAULT_MANIFEST,
        prepare.DEFAULT_OUTPUT,
    )
    assert len(materialized["documents"]) == 10
    assert all(Path(doc["path"]).is_file() for doc in materialized["documents"])


def test_paired_schemas_have_identical_extraction_target() -> None:
    source = json.loads(build_schemas.SOURCE_SCHEMA.read_text(encoding="utf-8"))
    standard, agentic = build_schemas.build_schema_pair(source)
    assert standard["fieldSchema"] == agentic["fieldSchema"]
    assert standard["models"]["completion"] == "gpt-4.1"
    assert "workflow" not in standard["config"]
    assert agentic["models"]["completion"] == "gpt-5.2"
    assert agentic["config"]["workflow"] == "Agentic"


def test_matching_is_one_to_one_and_uses_party_ties() -> None:
    quote = "Seller agrees to sell and Buyer agrees to purchase 100 units."
    predicted = [
        {
            "ObligorPartyId": "PRED-B",
            "ObligationType": "Payment",
            "Evidence": [{"ExactQuote": quote}],
        },
        {
            "ObligorPartyId": "PRED-S",
            "ObligationType": "Delivery",
            "Evidence": [{"ExactQuote": quote}],
        },
    ]
    gold = [
        {
            "obligation_id": "O001",
            "obligor_party_id": "GOLD-S",
            "obligation_type": "Delivery",
            "exact_quotes": [quote],
        },
        {
            "obligation_id": "O002",
            "obligor_party_id": "GOLD-B",
            "obligation_type": "Payment",
            "exact_quotes": [quote],
        },
    ]
    matches, extra, missing = evaluate.match_obligations(
        predicted,
        gold,
        {"PRED-S": "GOLD-S", "PRED-B": "GOLD-B"},
    )
    assert {(pred, target) for pred, target, _score in matches} == {(0, 1), (1, 0)}
    assert extra == []
    assert missing == []


def test_failed_document_scores_fail_closed() -> None:
    source_text = "Supplier shall deliver the goods."
    gold = {
        "doc_id": "sample",
        "parties": [],
        "obligations": [
            {
                "obligation_id": "O001",
                "obligor_party_id": "P1",
                "obligee_party_ids": ["P2"],
                "obligation_type": "Delivery",
                "nature": "Affirmative",
                "action": "Deliver the goods.",
                "business_summary": "Supplier must deliver the goods.",
                "exact_quotes": [source_text],
                "required_fields": [],
            }
        ],
    }
    result = evaluate.evaluate_document(gold, None, source_text)
    assert result["status"] == "failed"
    assert result["gold_count"] == 1
    assert result["predicted_count"] == 0
    assert result["matched_count"] == 0
    assert result["recall"] == 0.0


def test_missing_boolean_is_not_scored_as_false() -> None:
    source_text = "Supplier shall deliver the goods."
    gold = {
        "doc_id": "sample",
        "parties": [
            {
                "party_id": "P1",
                "legal_name": "Supplier",
                "aliases": [],
                "contract_role": "Supplier",
            },
            {
                "party_id": "P2",
                "legal_name": "Buyer",
                "aliases": [],
                "contract_role": "Buyer",
            },
        ],
        "obligations": [
            {
                "obligation_id": "O001",
                "obligor_party_id": "P1",
                "obligee_party_ids": ["P2"],
                "obligation_type": "Delivery",
                "nature": "Affirmative",
                "action": "Deliver the goods.",
                "business_summary": "Supplier must deliver the goods.",
                "exact_quotes": [source_text],
                "required_fields": [],
                "is_post_termination": False,
            }
        ],
    }
    prediction = {
        "parties": [
            {"PartyId": "A", "LegalName": "Supplier", "Aliases": []},
            {"PartyId": "B", "LegalName": "Buyer", "Aliases": []},
        ],
        "obligations": [
            {
                "ObligationId": "X1",
                "ObligorPartyId": "A",
                "ObligeePartyIds": ["B"],
                "ObligationType": "Delivery",
                "Nature": "Affirmative",
                "BusinessSummary": "Supplier must deliver the goods.",
                "Evidence": [{"ExactQuote": source_text}],
            }
        ],
    }
    run_record = {
        "status": "success",
        "error": "",
        "prediction": prediction,
        "elapsed_seconds": 1,
        "input_tokens": 1,
        "output_tokens": 1,
    }
    result = evaluate.evaluate_document(gold, run_record, source_text)
    assert result["matched_count"] == 1
    assert result["post_termination_present"] == 0
    assert result["post_termination_correct"] == 0


def test_reviewed_gold_is_internally_consistent() -> None:
    gold_path = PROJECT_DIR / "ground_truth" / "golden_obligations.jsonl"
    assert gold_path.is_file()
    records = evaluate.load_gold(gold_path)
    assert len(records) == 10
    for record in records:
        source_path = PROJECT_DIR / "samples" / "downloaded" / f"{record['doc_id']}.txt"
        source = source_path.read_text(encoding="utf-8")
        assert hashlib.sha256(source.encode("utf-8")).hexdigest() == record[
            "source_sha256"
        ]
        party_ids = {party["party_id"] for party in record["parties"]}
        obligation_ids = {
            obligation["obligation_id"] for obligation in record["obligations"]
        }
        assert record["annotation_metadata"]["review_status"] == "verified"
        for obligation in record["obligations"]:
            assert obligation["obligor_party_id"] in party_ids
            assert set(obligation["obligee_party_ids"]) <= party_ids
            assert set(obligation["related_obligation_ids"]) <= obligation_ids
            assert obligation["exact_quotes"]
            for span in obligation["source_spans"]:
                assert source[span["start"] : span["end"]] == span["text"]
            assert obligation["exact_quotes"] == [
                span["text"] for span in obligation["source_spans"]
            ]
