"""
PII Redaction Tool for PDFs using Azure AI Language Service

Extracts text from PDF, identifies PII using Azure AI Language PII API,
then creates a synthetic version by replacing PII with realistic fake values.

Usage:
    python redact_pii.py --input doc.pdf --output doc_redacted.pdf
    python redact_pii.py --input doc.pdf --output doc_redacted.pdf --report pii_report.json
    python redact_pii.py --input folder/ --output folder_redacted/

Features:
    - Uses Azure AI Language PII detection (same endpoint as CU)
    - Generates realistic fake replacements (not just asterisks)
    - Preserves PDF formatting by doing in-place text replacement
    - Produces a PII report documenting all found entities
    - Handles multi-page PDFs with chunked API calls (5120 char limit)
"""

import argparse
import json
import os
import random
import re
import string
import time
from pathlib import Path
from typing import Dict, List, Tuple

import fitz  # PyMuPDF
import requests
from dotenv import load_dotenv

# ─── Configuration ───────────────────────────────────────────────────────────

MAX_TEXT_CHUNK = 5120  # API limit per document
API_VERSION = "2023-04-01"
PII_CATEGORIES_TO_REDACT = [
    "Person",
    "PersonType",
    "Address",
    "PhoneNumber",
    "Email",
    "USSocialSecurityNumber",
    "USDriversLicenseNumber",
    "CreditCardNumber",
    "InternationalBankingAccountNumber",
    "SWIFTCode",
    "USBankAccountNumber",
    "Organization",
    "IPAddress",
    "DateTime",
    "URL",
]

# Categories to skip (too noisy / not real PII in legal docs)
PII_CATEGORIES_SKIP = [
    "Quantity",
    "DateTime",  # dates in legal forms are usually not PII
]


# ─── Fake Data Generators ────────────────────────────────────────────────────

FAKE_FIRST_NAMES = [
    "James", "Robert", "Patricia", "Jennifer", "Michael", "Linda", "William",
    "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Christopher", "Karen", "Daniel", "Lisa", "Matthew",
    "Nancy", "Anthony", "Betty", "Mark", "Margaret", "Donald", "Sandra",
]

FAKE_LAST_NAMES = [
    "Anderson", "Thompson", "Garcia", "Martinez", "Robinson", "Clark", "Lewis",
    "Walker", "Hall", "Allen", "Young", "Hernandez", "King", "Wright", "Lopez",
    "Hill", "Scott", "Green", "Adams", "Baker", "Nelson", "Carter", "Mitchell",
    "Perez", "Roberts", "Turner", "Phillips", "Campbell", "Parker", "Evans",
]

FAKE_STREETS = [
    "Oak Avenue", "Maple Drive", "Cedar Lane", "Pine Street", "Elm Boulevard",
    "Birch Road", "Willow Way", "Spruce Court", "Ash Circle", "Poplar Place",
]

FAKE_CITIES = [
    ("Springfield", "IL", "62701"), ("Riverside", "CA", "92501"),
    ("Franklin", "TN", "37064"), ("Madison", "WI", "53703"),
    ("Georgetown", "TX", "78626"), ("Bristol", "CT", "06010"),
    ("Arlington", "VA", "22201"), ("Fairview", "OR", "97024"),
    ("Salem", "MA", "01970"), ("Clinton", "MO", "64735"),
]

FAKE_CREDITOR_NAMES = [
    "Pacific Credit Services", "National Lending Corp", "Heritage Financial Group",
    "Summit Credit Union", "Premier Card Services", "Atlantic Banking Corp",
    "Cornerstone Capital", "Liberty Credit Corp", "Frontier Lending LLC",
    "Meridian Financial", "Beacon Credit Services", "Pinnacle Card Corp",
]


class FakeDataGenerator:
    """Generates consistent fake data (same input → same output within a run)."""

    def __init__(self, seed=42):
        self.rng = random.Random(seed)
        self.replacement_cache: Dict[str, str] = {}
        self._name_idx = 0
        self._creditor_idx = 0

    def get_replacement(self, text: str, category: str) -> str:
        """Get a fake replacement for detected PII. Returns same value for same input."""
        # Normalize key
        key = f"{category}::{text.strip().lower()}"
        if key in self.replacement_cache:
            return self.replacement_cache[key]

        replacement = self._generate(text, category)
        self.replacement_cache[key] = replacement
        return replacement

    def _generate(self, text: str, category: str) -> str:
        if category == "Person":
            return self._fake_person(text)
        elif category == "Address":
            return self._fake_address(text)
        elif category == "PhoneNumber":
            return self._fake_phone(text)
        elif category == "Email":
            return self._fake_email(text)
        elif category in ("USSocialSecurityNumber",):
            return self._fake_ssn(text)
        elif category in ("CreditCardNumber", "USBankAccountNumber"):
            return self._fake_account(text)
        elif category == "Organization":
            return self._fake_org(text)
        elif category == "URL":
            return "https://www.example.com"
        elif category == "IPAddress":
            return f"192.168.{self.rng.randint(1,254)}.{self.rng.randint(1,254)}"
        else:
            # Generic: preserve length with X's
            return "X" * len(text)

    def _fake_person(self, text: str) -> str:
        """Generate a fake person name matching the structure of the original."""
        parts = text.strip().split()
        fake_parts = []
        for i, part in enumerate(parts):
            if i == 0 or (len(parts) >= 3 and i == len(parts) - 1):
                # First or last name
                if i == 0:
                    fake_parts.append(self.rng.choice(FAKE_FIRST_NAMES))
                else:
                    fake_parts.append(self.rng.choice(FAKE_LAST_NAMES))
            elif len(parts) >= 3 and i == 1:
                # Middle name
                fake_parts.append(self.rng.choice(FAKE_FIRST_NAMES))
            else:
                fake_parts.append(self.rng.choice(FAKE_LAST_NAMES))

        result = " ".join(fake_parts)
        # Match casing
        if text.isupper():
            result = result.upper()
        return result

    def _fake_address(self, text: str) -> str:
        """Generate fake address preserving rough structure."""
        num = self.rng.randint(100, 9999)
        street = self.rng.choice(FAKE_STREETS)
        city, state, zipcode = self.rng.choice(FAKE_CITIES)

        # Check if it's a full address or just street
        if "," in text or any(s in text.upper() for s in [" AL ", " AK ", " AZ ", " AR ", " CA ", " CO ", " CT ", " DE ", " FL ", " GA ", " HI ", " ID ", " IL ", " IN ", " IA ", " KS ", " KY ", " LA ", " ME ", " MD ", " MA ", " MI ", " MN ", " MS ", " MO ", " MT ", " NE ", " NV ", " NH ", " NJ ", " NM ", " NY ", " NC ", " ND ", " OH ", " OK ", " OR ", " PA ", " RI ", " SC ", " SD ", " TN ", " TX ", " UT ", " VT ", " VA ", " WA ", " WV ", " WI ", " WY "]):
            return f"{num} {street}, {city}, {state} {zipcode}"
        elif any(c.isdigit() for c in text[:5]):
            return f"{num} {street}"
        else:
            return f"{city}, {state} {zipcode}"

    def _fake_phone(self, text: str) -> str:
        area = self.rng.randint(200, 999)
        prefix = self.rng.randint(200, 999)
        line = self.rng.randint(1000, 9999)
        if "(" in text:
            return f"({area}) {prefix}-{line}"
        elif "-" in text:
            return f"{area}-{prefix}-{line}"
        else:
            return f"{area}{prefix}{line}"

    def _fake_email(self, text: str) -> str:
        first = self.rng.choice(FAKE_FIRST_NAMES).lower()
        last = self.rng.choice(FAKE_LAST_NAMES).lower()
        return f"{first}.{last}@example.com"

    def _fake_ssn(self, text: str) -> str:
        return f"{self.rng.randint(100,999)}-{self.rng.randint(10,99)}-{self.rng.randint(1000,9999)}"

    def _fake_account(self, text: str) -> str:
        # Preserve length with random digits
        return "".join(
            str(self.rng.randint(0, 9)) if c.isdigit() else c
            for c in text
        )

    def _fake_org(self, text: str) -> str:
        self._creditor_idx = (self._creditor_idx + 1) % len(FAKE_CREDITOR_NAMES)
        result = FAKE_CREDITOR_NAMES[self._creditor_idx]
        if text.isupper():
            result = result.upper()
        return result


# ─── PII Detection ───────────────────────────────────────────────────────────

def detect_pii(text: str, endpoint: str, api_key: str) -> List[Dict]:
    """Detect PII entities in text using Azure AI Language API."""
    url = f"{endpoint}/language/:analyze-text?api-version={API_VERSION}"
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type": "application/json",
    }

    # Chunk text if needed
    chunks = []
    if len(text) <= MAX_TEXT_CHUNK:
        chunks = [(0, text)]
    else:
        # Split on newlines to avoid breaking mid-word
        lines = text.split("\n")
        current_chunk = ""
        current_offset = 0
        chunk_start = 0
        for line in lines:
            if len(current_chunk) + len(line) + 1 > MAX_TEXT_CHUNK:
                if current_chunk:
                    chunks.append((chunk_start, current_chunk))
                chunk_start = current_offset
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"
            current_offset += len(line) + 1
        if current_chunk:
            chunks.append((chunk_start, current_chunk))

    all_entities = []
    for chunk_offset, chunk_text in chunks:
        body = {
            "kind": "PiiEntityRecognition",
            "analysisInput": {
                "documents": [{"id": "1", "text": chunk_text, "language": "en"}]
            },
            "parameters": {"stringIndexType": "Utf16CodeUnit"},
        }

        response = requests.post(url, headers=headers, json=body, timeout=30)
        if response.status_code == 429:
            time.sleep(2)
            response = requests.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()

        result = response.json()
        docs = result.get("results", {}).get("documents", [])
        if docs:
            for entity in docs[0].get("entities", []):
                entity["offset"] += chunk_offset  # Adjust to full-text offset
                all_entities.append(entity)

    return all_entities


def detect_pii_in_pdf(pdf_path: Path, endpoint: str, api_key: str) -> Dict:
    """Extract text from PDF and detect PII on each page."""
    doc = fitz.open(str(pdf_path))
    pages_pii = {}
    all_unique_pii = {}

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        if not text.strip():
            continue

        entities = detect_pii(text, endpoint, api_key)

        # Filter to relevant categories
        filtered = [
            e for e in entities
            if e["category"] not in PII_CATEGORIES_SKIP
            and e["confidenceScore"] >= 0.7
        ]

        pages_pii[page_num + 1] = {
            "text_length": len(text),
            "entities": filtered,
        }

        for e in filtered:
            key = f"{e['category']}::{e['text'].lower()}"
            if key not in all_unique_pii:
                all_unique_pii[key] = {
                    "text": e["text"],
                    "category": e["category"],
                    "confidence": e["confidenceScore"],
                    "pages": [],
                }
            if page_num + 1 not in all_unique_pii[key]["pages"]:
                all_unique_pii[key]["pages"].append(page_num + 1)

    total_pages = len(doc)
    doc.close()
    return {
        "file": str(pdf_path.name),
        "total_pages": total_pages,
        "pages_with_pii": len(pages_pii),
        "unique_pii_count": len(all_unique_pii),
        "pages": pages_pii,
        "unique_entities": list(all_unique_pii.values()),
    }


# ─── PDF Redaction ───────────────────────────────────────────────────────────

def redact_pdf(
    pdf_path: Path, output_path: Path, endpoint: str, api_key: str,
    report_path: Path = None
) -> Dict:
    """Create a synthetic version of PDF with PII replaced by fake values."""
    print(f"  Detecting PII...")
    pii_report = detect_pii_in_pdf(pdf_path, endpoint, api_key)

    # Build replacement map
    faker = FakeDataGenerator(seed=42)
    replacement_map: Dict[str, str] = {}

    for entity_info in pii_report["unique_entities"]:
        original = entity_info["text"]
        category = entity_info["category"]
        replacement = faker.get_replacement(original, category)
        replacement_map[original] = replacement

    print(f"  Found {len(replacement_map)} unique PII values to replace")
    if replacement_map:
        # Show a few examples
        for i, (orig, repl) in enumerate(list(replacement_map.items())[:5]):
            print(f"    '{orig}' → '{repl}'")
        if len(replacement_map) > 5:
            print(f"    ... and {len(replacement_map) - 5} more")

    # Apply replacements to PDF
    print(f"  Creating synthetic PDF...")
    doc = fitz.open(str(pdf_path))

    # Sort replacements by length (longest first) to avoid partial matches
    sorted_replacements = sorted(replacement_map.items(), key=lambda x: -len(x[0]))

    replacements_made = 0
    for page_num in range(len(doc)):
        page = doc[page_num]
        for original, replacement in sorted_replacements:
            # Search for all instances of this text on the page
            instances = page.search_for(original)
            for inst in instances:
                # Redact by drawing white rect over original, then insert new text
                page.add_redact_annot(inst, replacement, fontsize=0, align=fitz.TEXT_ALIGN_LEFT)
                replacements_made += 1
        # Apply all redactions for this page
        page.apply_redactions()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()
    print(f"  ✓ Saved: {output_path} ({replacements_made} replacements)")

    # Add replacement map to report
    pii_report["replacements"] = {k: v for k, v in replacement_map.items()}
    pii_report["output_file"] = str(output_path.name)
    pii_report["total_replacements"] = replacements_made

    # Save report
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(pii_report, f, indent=2, ensure_ascii=False)
        print(f"  ✓ Report: {report_path}")

    return pii_report


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PII detection and redaction for PDFs")
    parser.add_argument("--input", type=Path, required=True, help="Input PDF or folder")
    parser.add_argument("--output", type=Path, required=True, help="Output PDF or folder")
    parser.add_argument("--report", type=Path, help="Save PII report JSON")
    parser.add_argument("--detect-only", action="store_true", help="Only detect PII, don't redact")
    args = parser.parse_args()

    load_dotenv()
    endpoint = os.getenv("AZURE_AI_ENDPOINT", "").rstrip("/")
    api_key = os.getenv("AZURE_AI_API_KEY", "")

    if not endpoint or not api_key:
        print("ERROR: Set AZURE_AI_ENDPOINT and AZURE_AI_API_KEY in .env")
        return

    if args.input.is_file():
        # Single file
        print(f"Processing: {args.input.name}")
        if args.detect_only:
            report = detect_pii_in_pdf(args.input, endpoint, api_key)
            out = args.report or args.output
            with open(out, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"  ✓ PII report: {out}")
            print(f"  Found {report['unique_pii_count']} unique PII entities")
        else:
            redact_pdf(args.input, args.output, endpoint, api_key, report_path=args.report)
    elif args.input.is_dir():
        # Folder of PDFs
        pdfs = sorted(args.input.glob("*.pdf"))
        if not pdfs:
            print(f"No PDFs found in {args.input}")
            return
        args.output.mkdir(parents=True, exist_ok=True)
        for pdf in pdfs:
            print(f"\n[{pdf.name}]")
            out_pdf = args.output / pdf.name
            report_path = args.output / f"{pdf.stem}_pii_report.json" if args.report is None else None
            if args.detect_only:
                report = detect_pii_in_pdf(pdf, endpoint, api_key)
                rpt = args.output / f"{pdf.stem}_pii_report.json"
                with open(rpt, "w", encoding="utf-8") as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
                print(f"  ✓ {report['unique_pii_count']} PII entities → {rpt.name}")
            else:
                redact_pdf(pdf, out_pdf, endpoint, api_key, report_path=report_path)
    else:
        print(f"ERROR: {args.input} not found")


if __name__ == "__main__":
    main()
