## 30-second elevator pitch

A migration assistant for Azure Content Understanding that ports analyzers from Preview to GA with less guesswork.

It scans one analyzer, a chosen set, or every analyzer in a resource.  
It rewrites analyzer definitions, migrates training data to `knowledgeSources`, flags lost features, and generates code-change guidance for app teams and GitHub Copilot. 

Details on how to do migration - https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/how-to/migration-preview-to-ga?tabs=portal
Details on how to move knowledge sources - https://github.com/jfilcik/azure-ai-content-understanding-python/blob/main/notebooks/move_training_data_across_analyzers.ipynb

## Problem & mission

Preview-to-GA migration is not just a find-and-replace job.

Teams must:
- update analyzer schema
- add GA model settings
- replace deprecated preview concepts
- create new analyzers
- update application calls for new request and upload patterns
- handle removed or changed features with judgment calls :contentReference[oaicite:1]{index=1}

### Mission

Make CU analyzer migration:
- fast
- repeatable
- reviewable
- safe for production teams

The tool should automate the obvious work and spotlight the risky work.

## Target audience

### Primary users
- Platform engineers managing shared CU resources
- App developers owning analyzer-integrated services
- AI engineering teams modernizing document, image, audio, or video workflows

### Secondary users
- Ops or admin teams running batch migrations across a resource
- Architects reviewing GA readiness and feature parity
- Developers using GitHub Copilot or coding agents to finish app-level changes

## Core features

### 1) Resource-wide discovery
- Connect to a CU resource the user can access
- List analyzers and key metadata
- Filter by analyzer ID, tag, type, status, or migration readiness
- Run on one analyzer, a selected set, or all analyzers in scope

### 2) Preview-to-GA analyzer conversion
- Fetch current analyzer definition
- Normalize preview schema into GA schema
- Replace deprecated `Scenario` mapping with GA `baseAnalyzerId`
- Add `models.completion` and `models.embedding`
- Prepare a GA-ready analyzer payload for creation as a new analyzer :contentReference[oaicite:2]{index=2}

### 3) Knowledge source migration
- Detect preview `trainingData`
- Convert it into GA-style `knowledgeSources`
- Reuse the existing blob storage location instead of copying data
- Preserve stable field mappings where possible
- Support the same-resource reuse pattern shown in the reference notebook :contentReference[oaicite:3]{index=3}

### 4) Feature-loss and judgment-call detection
Classify findings into:
- **Auto-fixed**
- **Needs review**
- **Not supported in GA**

Examples to flag:
- `AnalysisMode` / Pro mode removal
- Face API and person directory removal
- analyzer behavior differences from model changes
- app code still using old `analyze` payloads
- inline upload flows that must move to `analyzeBinary` :contentReference[oaicite:4]{index=4}

### 5) Diff and migration report
For each analyzer, show:
- source definition summary
- proposed GA definition summary
- field/schema differences
- config differences
- knowledge source migration status
- warnings, blockers, and recommended human decisions

### 6) Execution modes
- **Dry run**: inspect only
- **Generate artifacts**: export GA payloads and reports
- **Apply**: create new GA analyzers
- **Rollback helpers**: retain source analyzer references and exported backups

### 7) Developer handoff
Generate:
- Copilot-ready migration notes
- app-change checklist
- sample prompts for coding agents
- per-analyzer remediation summaries for pull requests or tickets

### 8) Simple UX
A small utility UI with three core screens:
- **Inventory**: analyzers in resource
- **Review**: diff, warnings, migration decisions
- **Run**: execute migration and export outputs

This stays intentionally light.  
The heavy lifting lives in the scriptable engine.

## High-level tech stack

### Migration engine
- **Python CLI**
  - Best fit for Azure auth, JSON transforms, batch processing, and CI use
  - Easy to run locally, in pipelines, or inside dev containers

### Azure access
- **Azure Identity**
  - Prefer Entra ID / `DefaultAzureCredential`
  - Support subscription key only as a fallback, matching common CU access patterns in community examples :contentReference[oaicite:5]{index=5}

### API integration
- **REST-first CU client**
  - Needed because migration requires direct access to analyzer definitions, defaults, and creation flows
  - Keeps the tool aligned with GA API behavior

### UX
- **Simple local web app**
  - Example fit: minimal React or a lightweight Python-hosted UI
  - Goal is review and execution, not enterprise workflow sprawl

### Output artifacts
- **Markdown + JSON**
  - Easy to inspect
  - Easy to commit
  - Easy to feed into Copilot, PRs, or change tickets

## Conceptual data model

### Resource
Represents one Azure Content Understanding resource.

Fields:
- resource name
- endpoint
- auth mode
- default model deployment status

### AnalyzerInventoryItem
A lightweight record used for listing and filtering.

Fields:
- analyzer ID
- base analyzer type
- status
- created date
- modified date
- tags
- migration state

### SourceAnalyzer
The raw Preview analyzer definition.

Fields:
- analyzer metadata
- config
- field schema
- training data
- warnings
- mode
- processing details

### ProposedGAAnalyzer
The transformed analyzer definition.

Fields:
- new analyzer ID
- GA `baseAnalyzerId`
- `models`
- transformed config
- field schema
- `knowledgeSources`
- validation results

### MigrationFinding
One issue or warning.

Fields:
- severity
- category
- message
- affected analyzer
- auto-fix status
- recommended action

### MigrationRun
One execution of the tool.

Fields:
- scope
- selected analyzers
- dry-run/apply mode
- outputs
- success count
- warning count
- failure count

## UI design principles

### Show the big picture first
Start with:
- total analyzers scanned
- ready to migrate
- needs review
- blocked

No deep JSON first.  
Users should know where the risk is in one glance.

### Make actions obvious
Each analyzer should offer only a few clear actions:
- Review
- Export
- Migrate
- Skip

### Keep the scary parts visible
Do not hide:
- removed GA features
- model assumptions
- API call changes
- knowledge source warnings

### Design for scanning
- short labels
- one-line summaries
- expandable detail only when needed
- plain-English status text

### Default to safe behavior
- dry run first
- explicit apply
- export backups before creation
- never overwrite silently

## Security & compliance notes

- Prefer Entra ID auth over subscription keys for production use. The community notebook also notes token-based auth as safer for production. :contentReference[oaicite:6]{index=6}
- Do not store secrets in exported reports.
- Mask blob URLs or sensitive paths in shareable outputs when possible.
- Log migration actions, but avoid logging full sensitive payloads by default.
- Require explicit confirmation for write operations.
- Respect least-privilege access to resources and storage-connected knowledge sources.

## Phased roadmap

### MVP
- Connect to one CU resource
- List analyzers
- Migrate one analyzer or a selected set
- Transform Preview schema to GA schema
- Convert `trainingData` to `knowledgeSources`
- Produce warnings for unsupported or changed features
- Export JSON + Markdown reports

### V1
- Resource-wide batch migration
- Dry run vs apply modes
- Rich diff view
- Model/default deployment checks
- Copilot-ready app migration notes
- CI-friendly CLI output and exit codes

### V2
- Multi-resource inventory
- Policy packs for migration standards
- Team review workflow
- PR/ticket generation
- Analyzer comparison and regression checklist
- Suggested fix prompts for coding agents

## Risks & mitigations

### Risk: false confidence from “successful” schema conversion
A valid payload does not guarantee equivalent behavior.

**Mitigation**
- mark semantic changes separately from syntax changes
- generate test checklist per analyzer
- require review for model and feature changes

### Risk: unsupported Preview features break parity
GA removes Pro mode, Face API, and person directory support. :contentReference[oaicite:7]{index=7}

**Mitigation**
- flag as hard warnings
- classify as “not supported in GA”
- suggest redesign paths instead of silent downgrade

### Risk: app code still calls old endpoints or payload shapes
GA changes `analyze` behavior and adds `analyzeBinary` for inline uploads. :contentReference[oaicite:8]{index=8}

**Mitigation**
- generate app integration checklist
- emit code-search hints
- export Copilot prompts for repository remediation

### Risk: training data migration assumptions
The reuse strategy depends on same-resource blob accessibility and compatible field IDs. The notebook’s pattern is explicitly based on reusing the existing blob storage location within the same resource. :contentReference[oaicite:9]{index=9}

**Mitigation**
- validate storage references before apply
- warn on field drift
- allow manual mapping review

### Risk: bulk migration causes operational confusion
Too many analyzers changed at once can overwhelm teams.

**Mitigation**
- batch by tag or folder
- support canary migrations
- keep source backups and migration manifests

## Future expansion ideas

- Analyzer regression pack generation
- Repo scanner for CU API usage
- “Fix my app” Copilot prompt generator
- Knowledge source inventory explorer
- Migration policy templates by workload type
- Support for portfolio-wide modernization dashboards