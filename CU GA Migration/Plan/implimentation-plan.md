## Build sequence

### Phase 0 — Align the migration contract
Goal: define exactly what the tool promises.

- Support three scopes:
  - single analyzer
  - selected analyzers
  - all analyzers in one CU resource
- Support three run modes:
  - dry run
  - export only
  - apply
- Define three finding classes:
  - auto-fixed
  - needs review
  - not supported in GA
- Lock the migration target to the GA API shape:
  - supported `baseAnalyzerId`
  - `models.completion`
  - `models.embedding`
  - `knowledgeSources` for labeled data :contentReference[oaicite:0]{index=0}

### Phase 1 — Build the inventory layer
Goal: see what exists before changing anything.

- Connect to one CU resource
- Authenticate with Entra ID first
- Add subscription-key fallback
- Fetch analyzer list
- Pull per-analyzer metadata
- Store a local snapshot for each analyzer
- Mark analyzers with a migration readiness status:
  - ready
  - review needed
  - blocked

### Phase 2 — Build the analyzer export pipeline
Goal: turn every source analyzer into a portable input object.

- Get analyzer definition via analyzer read call
- Normalize response shape into one internal model
- Capture:
  - analyzer ID
  - description
  - base analyzer / scenario clues
  - config
  - field schema
  - training data references
  - tags and timestamps
- Save raw JSON backup before any transform
- Save a trimmed summary for UI display

### Phase 3 — Build the Preview → GA transform engine
Goal: automate the obvious schema work.

- Map preview analyzer type to GA `baseAnalyzerId`
- Remove deprecated preview-only properties
- Add `models` block
- Validate presence of required model choices
- Preserve field schema where compatible
- Generate a proposed GA analyzer ID
- Create a structured transform log for each changed field

The GA doc explicitly requires:
- supported top-level `baseAnalyzerId`
- a new `models` object
- creation of a new analyzer rather than in-place reuse as the default path :contentReference[oaicite:1]{index=1}

### Phase 4 — Build the knowledge source migration module
Goal: carry labeled data forward without copying it.

- Detect analyzers using preview `TrainingData`
- Read storage-linked dataset details
- Convert the dataset definition into GA `knowledgeSources`
- Reuse the existing blob storage location where valid
- Preserve stable `fieldId` references where possible
- Flag field drift or broken storage references
- Output a migration note showing what was reused

This follows the same-resource reuse pattern shown in the reference notebook:
- no data duplication
- same resource access
- stable field portability when mappings still fit :contentReference[oaicite:2]{index=2}

### Phase 5 — Build the compatibility rules engine
Goal: catch the risky parts humans must review.

Rules to implement first:

- Flag deprecated `AnalysisMode`
- Flag Pro mode loss
- Flag Face API and person directory loss
- Flag content classifier / video segmentation remapping needs
- Flag app payloads that still assume old `analyze` behavior
- Flag inline upload patterns that must move to `analyzeBinary`
- Flag missing model deployment assumptions
- Flag any unresolved training-data to `knowledgeSources` conversion

The GA migration doc states:
- Pro mode is not in GA
- Face API and person directory are not in GA
- `TrainingData` is replaced by `knowledgeSources`
- `analyze` is URL-only, while inline upload moves to `analyzeBinary` :contentReference[oaicite:3]{index=3}

### Phase 6 — Build the validation layer
Goal: stop bad migrations before apply.

- Validate transformed schema shape
- Validate required top-level fields
- Validate `models` presence
- Validate `knowledgeSources` references
- Validate analyzer ID naming rules
- Validate model deployment names if defaults are expected
- Produce pass / warn / fail status

### Phase 7 — Build execution mode
Goal: create new analyzers safely.

- Add dry-run mode with zero writes
- Add export-only mode for JSON and Markdown
- Add apply mode for analyzer creation
- Create new analyzer instead of overwriting source
- Keep source analyzer untouched by default
- Write execution manifest with:
  - source analyzer
  - target analyzer
  - timestamp
  - run mode
  - result
  - warnings

### Phase 8 — Build developer handoff artifacts
Goal: help app teams finish the rest.

Generate per run:

- migration summary report
- analyzer-by-analyzer warning report
- app integration checklist
- repo search hints
- Copilot prompt pack
- coding-agent handoff notes

Examples of output sections:
- “Find code calling `analyze` with inline file content”
- “Replace old payload with GA `inputs[0].url`”
- “Move inline upload paths to `analyzeBinary`”
- “Review unsupported Preview features before release” :contentReference[oaicite:4]{index=4}

### Phase 9 — Build the simple UX
Goal: make review easy without turning this into a big platform.

#### Screen 1 — Inventory
Show:
- total analyzers
- selected analyzers
- ready
- review needed
- blocked

Actions:
- filter
- select
- export
- review

#### Screen 2 — Review
Show one analyzer at a time:
- source summary
- proposed GA summary
- warnings
- lost functionality
- judgment calls
- knowledge source status

Actions:
- accept
- skip
- rename target
- export note

#### Screen 3 — Run
Show:
- dry run / export / apply
- selected analyzers
- confirmation
- progress
- final status
- downloadable artifacts

### Phase 10 — Build test coverage
Goal: trust the tool before broad rollout.

Test sets:

- analyzer with simple document fields
- analyzer using preview training data
- analyzer with unsupported preview features
- analyzer with missing defaults
- analyzer that needs app-call changes
- batch migration with mixed outcomes

Test outputs:
- transformed JSON
- findings list
- execution manifest
- Copilot handoff text

## Timeline with checkpoints

### Week 1 — Foundation
- define internal analyzer model
- connect auth
- list analyzers
- export raw definitions
- create sample fixtures

Checkpoint:
- can inventory one resource and save source analyzer snapshots

### Week 2 — Core transform
- build Preview → GA mapper
- add `models` injection
- add analyzer ID strategy
- create diff output

Checkpoint:
- can produce a valid proposed GA payload for a simple analyzer

### Week 3 — Knowledge source migration
- detect preview training data
- convert to `knowledgeSources`
- validate storage references
- add field portability checks

Checkpoint:
- can migrate one training-data-backed analyzer using storage reuse strategy

### Week 4 — Rules and validation
- implement unsupported-feature rules
- implement judgment-call rules
- add pass / warn / fail scoring
- finalize export reports

Checkpoint:
- tool clearly separates auto-fixes from human review items

### Week 5 — Apply mode and UX
- add create-new-analyzer flow
- add run manifest
- build Inventory, Review, Run screens
- support export bundle download

Checkpoint:
- end-to-end dry run and apply flow works for a selected analyzer set

### Week 6 — Hardening
- batch tests
- edge-case cleanup
- error messages
- docs and usability pass
- pilot with real analyzers

Checkpoint:
- ready for internal trial on one production-like resource

## Team roles

### Product / migration owner
Owns:
- scope
- migration policy
- rollout order
- success criteria

### Lead engineer
Owns:
- migration engine
- API integration
- validation strategy
- release quality

### UX / product designer
Owns:
- Inventory, Review, Run flows
- wording of warnings
- high-signal defaults
- usability checks

### QA / test engineer
Owns:
- fixture coverage
- regression packs
- apply-mode safety tests
- export artifact verification

### Developer advocate or app liaison
Owns:
- Copilot handoff prompts
- app migration checklist
- repo remediation guidance
- onboarding docs for teams

## Recommended rituals

### Twice-weekly build review
30 minutes.

Review:
- blockers
- rule coverage
- migration edge cases
- UX confusion points

### Weekly migration clinic
45 minutes.

Bring:
- one real analyzer
- one failed transform
- one app integration issue

### Bi-weekly usability test
30 minutes.

Ask 3 users to:
- find blocked analyzers
- review one diff
- run a dry migration

Log the top 3 confusions.  
Fix those first.

### Release gate checklist
Before shipping apply mode:
- 5 real analyzers tested
- 1 training-data migration tested
- 1 unsupported-feature scenario tested
- all write operations require explicit confirmation
- rollback artifacts export cleanly

## Optional integrations

### GitHub Copilot handoff
Export prompts such as:
- update GA analyzer calls
- migrate inline upload code to `analyzeBinary`
- rewrite old `analyze` payload creation
- add test coverage for migrated analyzers

### CI integration
- run inventory nightly
- fail on blocked analyzers in selected scope
- publish migration reports as pipeline artifacts

### Ticketing integration
- create one ticket per blocked analyzer
- attach warnings and recommended action
- assign to owning team

### PR assistant mode
- attach analyzer diff summary to pull requests
- include app-call migration checklist
- include unsupported-feature warnings

## Stretch goals

### Repo scanner
Search code for:
- old `analyze` payload shapes
- inline binary upload patterns
- preview API versions
- analyzer IDs that changed

### Model readiness checker
Confirm resource defaults and required Foundry model deployments before apply.  
The GA prerequisites call for default model deployments and references to `GPT-4.1`, `GPT-4.1-mini`, and `text-embedding-3-large` depending on analyzer needs. :contentReference[oaicite:5]{index=5}

### Canary migration mode
- migrate 5 analyzers first
- compare outputs
- then expand to full resource

### Regression checklist generator
For each analyzer, generate:
- sample documents to test
- fields to verify
- confidence/source checks if enabled
- app endpoint changes to validate

## Definition of done

The tool is done for V1 when it can:

- inventory analyzers in one resource
- migrate one, many, or all selected analyzers
- convert preview schema to GA schema
- migrate `TrainingData` to `knowledgeSources` using storage reuse where valid
- flag unsupported features and judgment calls
- export actionable reports
- create new GA analyzers safely
- produce developer guidance for remaining app code changes