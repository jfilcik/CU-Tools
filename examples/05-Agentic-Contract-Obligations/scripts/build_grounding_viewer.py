"""Build a local HTML viewer for CU obligation evidence over source PDFs.

The generated viewer and copied source documents should be written beneath
``test_results/`` so contract content remains local and ignored by git.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


VALUE_KEYS = (
    "valueString",
    "valueNumber",
    "valueInteger",
    "valueBoolean",
    "valueDate",
    "valueTime",
    "valueCurrency",
    "valueAddress",
    "valueCountryRegion",
)
SOURCE_PATTERN = re.compile(r"^D\((\d+),(.+)\)$")
TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)


def unwrap_field(node: Any) -> Any:
    """Convert native CU typed field nodes to plain Python values."""
    if not isinstance(node, dict):
        return node
    if "valueArray" in node:
        return [unwrap_field(item) for item in node["valueArray"]]
    if "valueObject" in node:
        return {
            name: unwrap_field(value)
            for name, value in node["valueObject"].items()
        }
    for key in VALUE_KEYS:
        if key in node:
            return node[key]
    return None


def parse_source(source: str) -> tuple[int, list[float]] | None:
    """Parse a CU document polygon source such as D(2,x1,y1,...,x4,y4)."""
    match = SOURCE_PATTERN.match(source or "")
    if not match:
        return None
    try:
        coordinates = [float(value) for value in match.group(2).split(",")]
    except ValueError:
        return None
    if len(coordinates) < 4 or len(coordinates) % 2:
        return None
    return int(match.group(1)), coordinates


def normalized_tokens(value: str) -> list[str]:
    """Return punctuation-insensitive Unicode tokens for evidence matching."""
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    return TOKEN_PATTERN.findall(normalized)


def build_word_index(pages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, list[int]]]:
    """Flatten CU page words into searchable tokens with source rectangles."""
    tokens: list[dict[str, Any]] = []
    positions: dict[str, list[int]] = defaultdict(list)
    for page in pages:
        for word in page.get("words", []):
            parsed = parse_source(word.get("source", ""))
            if not parsed:
                continue
            page_number, coordinates = parsed
            xs = coordinates[0::2]
            ys = coordinates[1::2]
            rect = [min(xs), min(ys), max(xs), max(ys)]
            for token in normalized_tokens(str(word.get("content", ""))):
                positions[token].append(len(tokens))
                tokens.append({"token": token, "page": page_number, "rect": rect})
    return tokens, positions


def merge_line_rectangles(words: list[dict[str, Any]]) -> list[dict[str, float | int]]:
    """Merge adjacent matched word boxes into readable line highlights."""
    by_page: dict[int, list[list[float]]] = defaultdict(list)
    for word in words:
        by_page[int(word["page"])].append(list(word["rect"]))

    merged: list[dict[str, float | int]] = []
    for page_number, rects in sorted(by_page.items()):
        rects.sort(key=lambda rect: (rect[1], rect[0]))
        lines: list[list[float]] = []
        for rect in rects:
            if lines:
                current = lines[-1]
                vertical_overlap = min(current[3], rect[3]) - max(current[1], rect[1])
                min_height = min(current[3] - current[1], rect[3] - rect[1])
                same_line = vertical_overlap >= min_height * 0.45
                close_enough = rect[0] <= current[2] + 0.2
                if same_line and close_enough:
                    current[0] = min(current[0], rect[0])
                    current[1] = min(current[1], rect[1])
                    current[2] = max(current[2], rect[2])
                    current[3] = max(current[3], rect[3])
                    continue
            lines.append(rect[:])
        for left, top, right, bottom in lines:
            merged.append(
                {
                    "page": page_number,
                    "x": round(left, 4),
                    "y": round(top, 4),
                    "width": round(right - left, 4),
                    "height": round(bottom - top, 4),
                }
            )
    return merged


def locate_quote(
    quote: str,
    words: list[dict[str, Any]],
    positions: dict[str, list[int]],
) -> list[dict[str, float | int]]:
    """Locate an exact evidence quote in CU words and return merged rectangles."""
    quote_tokens = normalized_tokens(quote)
    if not quote_tokens:
        return []
    for start in positions.get(quote_tokens[0], []):
        end = start + len(quote_tokens)
        if end > len(words):
            continue
        if [word["token"] for word in words[start:end]] == quote_tokens:
            return merge_line_rectangles(words[start:end])
    return []


def result_content(raw: dict[str, Any]) -> dict[str, Any]:
    result = raw.get("result", raw)
    contents = result.get("contents", []) if isinstance(result, dict) else []
    return contents[0] if contents else {}


def load_result_map(result_dirs: list[Path]) -> tuple[dict[str, Path], dict[str, dict[str, Any]]]:
    """Map document stems to result files and metadata outcomes."""
    result_files: dict[str, Path] = {}
    outcomes: dict[str, dict[str, Any]] = {}
    for result_dir in result_dirs:
        metadata_path = result_dir / "metadata.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            for item in metadata.get("results", []):
                outcomes[Path(item.get("document", "")).stem.casefold()] = item
        for path in result_dir.glob("*.json"):
            if path.name not in {"metadata.json", "selection_manifest.json", "recovery.json"}:
                result_files[path.stem.casefold()] = path
    return result_files, outcomes


def render_pdf(pdf_path: Path, asset_dir: Path, scale: float) -> list[str]:
    """Render every PDF page to a local JPEG asset."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required. Install repository requirements.") from exc

    page_dir = asset_dir / pdf_path.stem
    page_dir.mkdir(parents=True, exist_ok=True)
    image_paths: list[str] = []
    with fitz.open(pdf_path) as document:
        for index, page in enumerate(document):
            output_path = page_dir / f"page-{index + 1:04d}.jpg"
            if not output_path.exists():
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                pixmap.save(output_path, jpg_quality=78)
            image_paths.append(output_path.as_posix())
    return image_paths


def build_document(
    pdf_path: Path,
    result_path: Path | None,
    outcome: dict[str, Any] | None,
    output_dir: Path,
    scale: float,
) -> dict[str, Any]:
    """Create one browser-ready document record and local page assets."""
    slug = re.sub(r"[^a-z0-9]+", "-", pdf_path.stem.casefold()).strip("-")
    document_asset_dir = output_dir / "assets" / slug
    document_asset_dir.mkdir(parents=True, exist_ok=True)
    copied_pdf = document_asset_dir / "source.pdf"
    shutil.copy2(pdf_path, copied_pdf)

    rendered = render_pdf(pdf_path, output_dir / "assets", scale)
    relative_pages = [
        str(Path(path).relative_to(output_dir)).replace("\\", "/")
        for path in rendered
    ]
    record: dict[str, Any] = {
        "id": slug,
        "name": pdf_path.name,
        "pdf": str(copied_pdf.relative_to(output_dir)).replace("\\", "/"),
        "pages": relative_pages,
        "pageGeometry": [],
        "metadata": {},
        "parties": [],
        "obligations": [],
        "status": (outcome or {}).get("status", "missing-result"),
        "error": (outcome or {}).get("error", ""),
    }
    if not result_path:
        return record

    raw = json.loads(result_path.read_text(encoding="utf-8"))
    content = result_content(raw)
    fields = content.get("fields", {})
    pages = content.get("pages", [])
    words, positions = build_word_index(pages)
    record["status"] = raw.get("status", "Succeeded").casefold()
    record["pageGeometry"] = [
        {
            "page": page.get("pageNumber"),
            "width": page.get("width"),
            "height": page.get("height"),
        }
        for page in pages
    ]
    record["metadata"] = unwrap_field(fields.get("ContractMetadata", {})) or {}
    record["parties"] = unwrap_field(fields.get("Parties", {})) or []

    obligations = unwrap_field(fields.get("Obligations", {})) or []
    for obligation in obligations:
        evidence_records = []
        for evidence in obligation.get("Evidence") or []:
            quote = str(evidence.get("ExactQuote") or "")
            rectangles = locate_quote(quote, words, positions)
            evidence_records.append(
                {
                    **evidence,
                    "rectangles": rectangles,
                    "pages": sorted({int(rect["page"]) for rect in rectangles}),
                    "matched": bool(rectangles),
                }
            )
        record["obligations"].append({**obligation, "Evidence": evidence_records})
    return record


def viewer_html(title: str, documents: list[dict[str, Any]]) -> str:
    """Return a self-contained HTML shell with embedded viewer data."""
    data = json.dumps(documents, ensure_ascii=False).replace("<", "\\u003c")
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>
:root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #eef1f5; color: #172033; }}
header {{ height: 58px; display: flex; align-items: center; gap: 14px; padding: 8px 16px; background: #172033; color: white; }}
header h1 {{ font-size: 17px; margin: 0; white-space: nowrap; }}
select, input, button {{ font: inherit; }}
select, input {{ border: 1px solid #cad0dc; border-radius: 6px; padding: 8px; background: white; }}
#doc-select {{ min-width: 360px; max-width: 42vw; }}
.layout {{ height: calc(100vh - 58px); display: grid; grid-template-columns: 390px minmax(0, 1fr); }}
aside {{ display: flex; flex-direction: column; border-right: 1px solid #cad0dc; background: white; min-height: 0; }}
.summary {{ padding: 12px; border-bottom: 1px solid #e2e6ed; font-size: 13px; }}
.summary strong {{ display: block; font-size: 15px; margin-bottom: 5px; }}
.filters {{ display: flex; gap: 8px; padding: 10px; border-bottom: 1px solid #e2e6ed; }}
.filters input {{ width: 100%; }}
#obligations {{ overflow: auto; padding: 8px; }}
.obligation {{ width: 100%; text-align: left; border: 1px solid #d8dde6; border-radius: 8px; background: white; padding: 10px; margin-bottom: 8px; cursor: pointer; }}
.obligation:hover, .obligation.active {{ border-color: #5b55d6; box-shadow: 0 0 0 1px #5b55d6; }}
.obligation .id {{ color: #5b55d6; font-weight: 700; }}
.obligation .type {{ float: right; color: #526078; font-size: 11px; }}
.obligation p {{ margin: 7px 0 0; line-height: 1.35; }}
main {{ display: grid; grid-template-columns: minmax(0, 1fr) 350px; min-width: 0; }}
.document {{ display: flex; flex-direction: column; min-width: 0; min-height: 0; }}
.toolbar {{ display: flex; justify-content: center; align-items: center; gap: 9px; min-height: 48px; background: white; border-bottom: 1px solid #d8dde6; }}
.toolbar a {{ color: #514bc4; margin-left: 14px; }}
.page-scroll {{ overflow: auto; padding: 18px; text-align: center; }}
.page {{ position: relative; display: inline-block; line-height: 0; box-shadow: 0 4px 18px #26334b33; background: white; }}
.page img {{ max-width: 100%; height: auto; }}
.highlight {{ position: absolute; background: #ffdf3d66; border: 2px solid #f09c00; border-radius: 2px; pointer-events: none; }}
.details {{ overflow: auto; padding: 14px; background: #f9fafc; border-left: 1px solid #d8dde6; }}
.details h2 {{ font-size: 16px; margin: 0 0 8px; }}
.details dl {{ display: grid; grid-template-columns: 90px 1fr; gap: 5px; font-size: 12px; }}
.details dt {{ font-weight: 700; color: #526078; }}
.details dd {{ margin: 0; }}
.evidence {{ background: white; border-left: 4px solid #5b55d6; padding: 10px; margin: 12px 0; font-size: 13px; line-height: 1.4; }}
.evidence.unmatched {{ border-color: #c75c36; }}
.page-link {{ border: 0; color: #514bc4; background: transparent; cursor: pointer; padding: 4px 0; }}
.empty {{ color: #68758b; padding: 18px; text-align: center; }}
@media (max-width: 1050px) {{ .layout {{ grid-template-columns: 320px 1fr; }} main {{ grid-template-columns: 1fr; }} .details {{ display: none; }} }}
</style>
</head>
<body>
<header>
  <h1>{safe_title}</h1>
  <select id="doc-select" aria-label="Contract"></select>
</header>
<div class="layout">
  <aside>
    <div class="summary" id="summary"></div>
    <div class="filters"><input id="search" type="search" placeholder="Filter obligations"></div>
    <div id="obligations"></div>
  </aside>
  <main>
    <section class="document">
      <div class="toolbar">
        <button id="previous" type="button">Previous</button>
        <span>Page <input id="page-number" type="number" min="1" value="1" style="width:72px"> / <span id="page-count">0</span></span>
        <button id="next" type="button">Next</button>
        <a id="open-pdf" target="_blank" rel="noopener">Open PDF</a>
      </div>
      <div class="page-scroll"><div class="page" id="page"><img id="page-image" alt="Rendered contract page"><div id="overlays"></div></div></div>
    </section>
    <section class="details" id="details"><div class="empty">Select an obligation to inspect its evidence.</div></section>
  </main>
</div>
<script id="viewer-data" type="application/json">{data}</script>
<script>
const documents = JSON.parse(document.getElementById("viewer-data").textContent);
const state = {{ document: documents[0], obligation: null, page: 1 }};
const byId = id => document.getElementById(id);
const docSelect = byId("doc-select");

function text(value) {{ return value === null || value === undefined || value === "" ? "—" : String(value); }}
function partyName(id) {{
  const party = (state.document.parties || []).find(item => item.PartyId === id);
  return party ? `${{party.LegalName}} (${{id}})` : text(id);
}}
function geometry(page) {{
  return (state.document.pageGeometry || []).find(item => item.page === page) || {{width: 1, height: 1}};
}}
function setPage(page) {{
  state.page = Math.max(1, Math.min(Number(page) || 1, state.document.pages.length || 1));
  byId("page-number").value = state.page;
  byId("page-count").textContent = state.document.pages.length;
  byId("page-image").src = state.document.pages[state.page - 1] || "";
  drawOverlays();
}}
function drawOverlays() {{
  const host = byId("overlays");
  host.replaceChildren();
  if (!state.obligation) return;
  const size = geometry(state.page);
  for (const evidence of state.obligation.Evidence || []) {{
    for (const rect of evidence.rectangles || []) {{
      if (rect.page !== state.page) continue;
      const node = document.createElement("div");
      node.className = "highlight";
      node.style.left = `${{rect.x / size.width * 100}}%`;
      node.style.top = `${{rect.y / size.height * 100}}%`;
      node.style.width = `${{rect.width / size.width * 100}}%`;
      node.style.height = `${{rect.height / size.height * 100}}%`;
      host.append(node);
    }}
  }}
}}
function renderDetails() {{
  const host = byId("details");
  host.replaceChildren();
  if (!state.obligation) {{
    host.innerHTML = '<div class="empty">Select an obligation to inspect its evidence.</div>';
    return;
  }}
  const item = state.obligation;
  const title = document.createElement("h2");
  title.textContent = `${{text(item.ObligationId)}} · ${{text(item.ObligationType)}}`;
  host.append(title);
  const dl = document.createElement("dl");
  const rows = [
    ["Obligor", partyName(item.ObligorPartyId)],
    ["Obligees", (item.ObligeePartyIds || []).map(partyName).join(", ") || "—"],
    ["Nature", text(item.Nature)],
    ["Timing", text(item.Timing)],
    ["Amount", text(item.AmountOrQuantity)],
    ["Trigger", text(item.TriggerCondition)],
    ["Exceptions", text(item.Exceptions)]
  ];
  for (const [label, value] of rows) {{
    const dt = document.createElement("dt"); dt.textContent = label;
    const dd = document.createElement("dd"); dd.textContent = value;
    dl.append(dt, dd);
  }}
  host.append(dl);
  const summary = document.createElement("p");
  summary.textContent = text(item.BusinessSummary);
  host.append(summary);
  for (const evidence of item.Evidence || []) {{
    const card = document.createElement("div");
    card.className = `evidence${{evidence.matched ? "" : " unmatched"}}`;
    const quote = document.createElement("div");
    quote.textContent = `“${{text(evidence.ExactQuote)}}”`;
    card.append(quote);
    const source = document.createElement("small");
    source.textContent = `${{text(evidence.EvidencePurpose)}} · ${{text(evidence.SourceReference)}}`;
    card.append(source);
    if (evidence.pages && evidence.pages.length) {{
      const button = document.createElement("button");
      button.className = "page-link";
      button.textContent = `Show on page ${{evidence.pages.join(", ")}}`;
      button.onclick = () => setPage(evidence.pages[0]);
      card.append(document.createElement("br"), button);
    }} else {{
      const warning = document.createElement("small");
      warning.textContent = " Quote could not be aligned to CU word geometry.";
      card.append(document.createElement("br"), warning);
    }}
    host.append(card);
  }}
}}
function selectObligation(item, button) {{
  state.obligation = item;
  document.querySelectorAll(".obligation").forEach(node => node.classList.remove("active"));
  button.classList.add("active");
  const firstPage = (item.Evidence || []).flatMap(evidence => evidence.pages || [])[0];
  if (firstPage) setPage(firstPage); else drawOverlays();
  renderDetails();
}}
function renderObligations() {{
  const host = byId("obligations");
  host.replaceChildren();
  const query = byId("search").value.trim().toLocaleLowerCase();
  const items = (state.document.obligations || []).filter(item =>
    !query || JSON.stringify(item).toLocaleLowerCase().includes(query)
  );
  for (const item of items) {{
    const button = document.createElement("button");
    button.className = "obligation";
    const header = document.createElement("div");
    const id = document.createElement("span"); id.className = "id"; id.textContent = text(item.ObligationId);
    const type = document.createElement("span"); type.className = "type"; type.textContent = text(item.ObligationType);
    const summary = document.createElement("p"); summary.textContent = text(item.BusinessSummary);
    header.append(id, type); button.append(header, summary);
    button.onclick = () => selectObligation(item, button);
    host.append(button);
  }}
  if (!items.length) host.innerHTML = '<div class="empty">No obligations available.</div>';
}}
function selectDocument(index) {{
  state.document = documents[index];
  state.obligation = null;
  state.page = 1;
  byId("open-pdf").href = state.document.pdf;
  const matched = (state.document.obligations || []).flatMap(item => item.Evidence || []).filter(item => item.matched).length;
  const total = (state.document.obligations || []).flatMap(item => item.Evidence || []).length;
  byId("summary").innerHTML = `<strong>${{state.document.name}}</strong>${{state.document.obligations.length}} obligations · ${{matched}}/${{total}} evidence quotes aligned · status: ${{state.document.status}}${{state.document.error ? `<br>${{state.document.error}}` : ""}}`;
  byId("search").value = "";
  renderObligations();
  renderDetails();
  setPage(1);
}}
documents.forEach((item, index) => {{
  const option = document.createElement("option");
  option.value = index;
  option.textContent = `${{item.name}} (${{item.obligations.length}} obligations)`;
  docSelect.append(option);
}});
docSelect.onchange = () => selectDocument(Number(docSelect.value));
byId("search").oninput = renderObligations;
byId("previous").onclick = () => setPage(state.page - 1);
byId("next").onclick = () => setPage(state.page + 1);
byId("page-number").onchange = event => setPage(event.target.value);
byId("page-image").onload = drawOverlays;
selectDocument(0);
</script>
</body>
</html>
"""


def parse_paths(values: list[str]) -> list[Path]:
    paths = [Path(value).resolve() for value in values]
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise ValueError(f"Path does not exist: {missing[0]}")
    return paths


def prepare_output_dir(output_dir: Path) -> None:
    """Remove stale viewer assets so omitted contracts cannot remain exposed."""
    asset_dir = output_dir / "assets"
    if asset_dir.exists():
        shutil.rmtree(asset_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a local HTML viewer with obligation evidence overlays."
    )
    parser.add_argument("--pdf-dir", action="append", required=True)
    parser.add_argument("--result-dir", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", default="Contract obligation grounding viewer")
    parser.add_argument(
        "--render-scale",
        type=float,
        default=1.4,
        help="PDF page rendering scale (default: 1.4, approximately 101 DPI)",
    )
    args = parser.parse_args()

    pdf_dirs = parse_paths(args.pdf_dir)
    result_dirs = parse_paths(args.result_dir)
    output_dir = Path(args.output).resolve()
    prepare_output_dir(output_dir)
    result_files, outcomes = load_result_map(result_dirs)

    pdf_paths = sorted(
        (path for directory in pdf_dirs for path in directory.glob("*.pdf")),
        key=lambda path: path.name.casefold(),
    )
    if not pdf_paths:
        raise ValueError("No PDF files found.")

    documents = []
    for index, pdf_path in enumerate(pdf_paths, 1):
        key = pdf_path.stem.casefold()
        print(f"[{index}/{len(pdf_paths)}] Building {pdf_path.name}", flush=True)
        documents.append(
            build_document(
                pdf_path,
                result_files.get(key),
                outcomes.get(key),
                output_dir,
                args.render_scale,
            )
        )

    index_path = output_dir / "index.html"
    index_path.write_text(viewer_html(args.title, documents), encoding="utf-8")
    print(f"Viewer: {index_path}")


if __name__ == "__main__":
    main()
