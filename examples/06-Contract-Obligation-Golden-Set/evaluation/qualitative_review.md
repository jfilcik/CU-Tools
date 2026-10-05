# Standard vs. Agentic qualitative obligation review

**Verdict:** Agentic materially improves recall and practical clause discovery, but it does not deliver a compelling balanced-quality or production-readiness win on this run.

**Demo:** Reasonable as a candid recall-oriented demo with side-by-side evidence and human review. Not reasonable if presented as broadly superior, inexpensive, fast, or production ready.

**Production:** Neither mode is a standalone production approach for a complete atomic obligation register. Standard is too incomplete; Agentic is too noisy, slow, token-heavy, and schema-incomplete: IsPostTermination is populated on only 5.6% of matched outputs.

## Scope and method

This review covers all 10 contracts and 97 reviewed gold obligations. It rechecks every Agentic selected match, all 25 deterministic misses, and all 57 unmatched Agentic predictions against the source text. Post-termination metrics use corrected fail-closed handling: a missing boolean is uncovered and incorrect. The gold set was not changed.

## Headline metrics

| Metric | Standard | Agentic | Delta / ratio |
|---|---:|---:|---:|
| Completion | 100.0% | 100.0% | +0.0% |
| Precision | 78.2% | 55.8% | -22.4% |
| Recall | 44.3% | 74.2% | +29.9% |
| F1 | 56.6% | 63.7% | +7.1% |
| Type accuracy | 81.4% | 79.2% | -2.2% |
| Nature accuracy | 48.8% | 68.1% | +19.2% |
| Obligor accuracy | 88.4% | 83.3% | -5.0% |
| Obligee accuracy | 65.1% | 62.5% | -2.6% |
| Post-termination accuracy | 95.3% | 5.6% | -89.8% |
| Post-termination coverage | 100.0% | 5.6% | -94.4% |
| Required-detail accuracy | 28.6% | 33.1% | +4.6% |
| Quote groundedness | 100.0% | 98.2% | -1.8% |
| Predicted obligations | 55 | 129 | +74 |
| Matched obligations | 43 | 72 | +29 |
| Mean latency | 19.7 s | 272.2 s | 13.8× |
| p95 latency | 27.0 s | 468.8 s | 17.4× |
| Total tokens | 56,768 | 1,770,220 | 31.2× |

Agentic adds **29.9 recall points** but loses **22.4 precision points**. F1 improves only **7.1 points**, below the evaluator’s predeclared 10-point material-advantage threshold. Its **5.6% IsPostTermination coverage** is a material schema-completeness failure. Both runs completed all documents.

## Findings suitable for the benchmark report

- Standard is not a total failure: it is fast (19.7 s mean), 78.2% precise, and 100% quote-grounded, but 44.3% atomic recall makes it unsuitable for exhaustive obligation inventories.
- Agentic raises atomic recall from 44.3% to 74.2% and reduces true source-content misses from 33 to 5, a material discovery improvement.
- Balanced quality improves modestly: F1 moves from 56.6% to 63.7% (+7.1 points), below the evaluator's 10-point material-advantage threshold.
- Of 25 Agentic false negatives, 20 are one-to-one/atomicity non-matches with 1.0 quote support in an already-matched prediction; only 5 are true unrepresented duties.
- Of 57 Agentic unmatched predictions, 41 are genuine rights/options/grants/facts/legal effects, 8 are valid alternate atomization, 5 are duplicate fragments, 3 are quote/evaluator artifacts, and 0 are high-confidence gold omissions.
- Deterministic 55.8% precision is conservative for source-supported usefulness but directionally fair for raw atomic output: reviewed useful yield is roughly 61-64%, or 67% if redundant fragments count.
- Agentic quote groundedness is effectively strong: the reported 98.2% reflects three Prime quotes differing only by an extra trailing quotation mark, not invented substantive text.
- Agentic has a material schema-completeness failure: IsPostTermination effective accuracy and coverage are both 5.6% (4/72 present and correct), versus Standard 95.3% accuracy and 100% coverage (43/43 present).
- Agentic costs are large: 13.8x mean latency, 17.4x p95 latency, and 31.2x total tokens versus Standard.
- The next evidence-producing step should test a stricter obligation ontology/atomic schema and improved matching, then separately test a Standard-first Agentic-fallback cascade; no improvement from those unrun changes is claimed.

## Does Standard work?

Yes—within a limited role. Standard is fast, fully grounded, and comparatively precise. It does **not** work as an exhaustive broad-obligation inventory: only 43/97 atoms match, 33 gold duties have no Standard quote candidate, and reciprocal/responsibility-framed duties are systematically absent. Calling Standard a total failure would ignore its useful triage behavior; calling it complete would ignore the evidence.

## Does Agentic materially help?

Agentic **materially helps discovery**: true unrepresented gold duties fall from 33 to 5, and quote-supported clause coverage rises from 64/97 (66.0%) to 92/97 (94.8%). It does **not** establish a material balanced-quality advantage: F1 rises 7.1 rather than 10 points, precision is 55.8%, IsPostTermination coverage is 5.6%, and cost grows sharply. It is a credible recall demo, not a production-readiness result.

## How to interpret Agentic precision and recall

- **Recall (74.2%) is fair for the requested atomic schema**, but conservative for clause discovery: 20/25 misses are merged-sibling one-to-one failures with 1.0 quote support.
- **Recall also slightly overstates semantic atom correctness** because the TransMontaigne collateral-assignment exception/right is counted as gold O007 prohibition.
- **Precision (55.8%) is conservative but directionally fair.** Of 57 unmatched predictions, 16 are alternate atoms, fragments, or evaluator artifacts; nevertheless all 57 add reconciliation work and 41 are genuine non-obligations.
- A reviewed useful-yield range is about **61–64%** excluding redundant fragments, or **67%** if fragments count as source-supported. These are diagnostics, not replacement benchmark metrics.

## Schema completeness: `IsPostTermination`

| Mode | Present / matched | Coverage | Correct / matched | Effective accuracy |
|---|---:|---:|---:|---:|
| Standard | 43/43 | 100.0% | 41/43 | 95.3% |
| Agentic | 4/72 | 5.6% | 4/72 | 5.6% |

All four populated Agentic values are correct, but 68/72 matched outputs omit the boolean entirely. This is not a classification mistake among populated values; it is a material schema-completeness failure. The corrected evaluator appropriately fails closed instead of treating missing values as `false`.

## Agentic unmatched-prediction taxonomy

| Classification | Count | Interpretation |
|---|---:|---|
| `genuine_unsupported_right_option_or_factual_over_extraction` | 41 | Rights, options, grants, facts, representations, legal effects, acknowledgements, or passive formalities—not performance obligations. |
| `valid_obligation_omitted_by_gold` | 0 | High-confidence source obligation absent from gold. |
| `valid_alternate_atomization_of_existing_gold` | 8 | Useful detail/action already represented by a gold parent. |
| `duplicate_or_fragmentation` | 5 | Redundant preamble or list-item fragment. |
| `quote_or_evaluator_artifact` | 3 | Valid context/detail penalized by evidence span or greedy pairing. |

No high-confidence omitted gold obligation was found. The 41 genuine extras split into 19 rights/options/present grants or conveyances and 22 facts/legal effects/representations/acknowledgements/formalities.

## False-negative composition

| Mode | Deterministic FN | Atomicity / one-to-one | True source-content miss |
|---|---:|---:|---:|
| Standard | 54 | 21 | 33 |
| Agentic | 25 | 20 | 5 |

Agentic nearly eliminates clause omissions but still under-splits reciprocal parties and coordinated actions. The five true Agentic misses are Xlite O001 and PreCheck O001/O002/O006/O007; PreCheck O006/O007 were found by Standard, so Agentic is not a strict superset.

## Per-contract comparison

| Contract | Standard matched | Agentic matched | Agentic P / R | Agentic atomic FN | Agentic true FN | Clause support |
|---|---:|---:|---:|---:|---:|---:|
| Galacticomm | 3/6 | 4/6 | 57.1% / 66.7% | 2 | 0 | 6/6 |
| Watchit | 8/9 | 9/9 | 75.0% / 100.0% | 0 | 0 | 9/9 |
| Pacific | 4/6 | 5/6 | 71.4% / 83.3% | 1 | 0 | 6/6 |
| Prime | 4/4 | 4/4 | 50.0% / 100.0% | 0 | 0 | 4/4 |
| Verso | 1/2 | 1/2 | 50.0% / 50.0% | 1 | 0 | 2/2 |
| RGC | 3/7 | 5/7 | 83.3% / 71.4% | 2 | 0 | 7/7 |
| Xlite | 3/15 | 10/15 | 45.5% / 66.7% | 4 | 1 | 14/15 |
| Gridiron | 5/16 | 10/16 | 47.6% / 62.5% | 6 | 0 | 16/16 |
| TransMontaigne | 4/11 | 7/11 | 38.9% / 63.6% | 4 | 0 | 11/11 |
| PreCheck | 8/21 | 17/21 | 65.4% / 81.0% | 0 | 4 | 17/21 |

### Galacticomm

Agentic splits weekly remittance from rates, improving 3 to 4 matches, but still merges first/second price tiers and support staffing/availability. Its three extras are prior-agreement legal effect, passive no-fee language, and the purchase option.

### Watchit

Agentic reaches 9/9 and correctly emits both pre-publicity discussion sides; Standard collapsed them. All three extras are explicit rights/options, so the recall win is real but precision loss is avoidable ontology leakage.

### Pacific

Agentic finds the mediation clause Standard missed, but emits one parties-level record, so one reciprocal gold side remains unmatched. The passive excerpt-approval clause still has the wrong obligor, and two legal-effect clauses are over-extracted.

### Prime

Both modes find all four gold duties. Agentic adds useful expiry and liquidity-adjustment atoms plus two factual/legal-effect records, moving precision to 50%. Detail accuracy improves from 2/14 to 5/14 but remains poor; three quote failures are trailing-mark artifacts.

### Verso

No discovery improvement: both modes capture Seller further assurances but fail to emit Backhaul cost-bearing separately and both treat the effective present conveyance as a duty. Agentic is far slower and more expensive for the same 1/2 atomic result.

### RGC

Agentic improves 3 to 5 matches and has source support for all seven duties. It separates office duration/hours but merges base/future fee atoms and both notice sides. The only unmatched prediction is the present franchise grant.

### Xlite

Agentic produces the largest substantive gain: 10 matches versus Standard 3 and 14/15 clause support, finding costs, manufacturing/delivery, pricing approval, and split confidentiality. It also emits 11 genuine rights/facts/legal effects and one confidentiality preamble fragment; atomic indemnity and responsibility splitting remain incomplete.

### Gridiron

Agentic has source support for all 16 gold duties and doubles deterministic matches from 5 to 10. Five unmatched records are valid alternate product/price/sample atoms and two are notice-address evidence artifacts; four are genuine non-obligations. Reciprocal notices, indemnity verbs, and termination confidentiality remain merged.

### TransMontaigne

Agentic covers all gold clauses and increases matches from 4 to 7, but heavily fragments reimbursement into list items. Greedy matching assigns O003 to a tax fragment and leaves the correct broad reimbursement record unmatched. The exception-only collateral-assignment right is incorrectly counted as O007, so the nominal recall slightly overstates atomic correctness.

### PreCheck

Agentic rises from 8 to 17 matches, correctly expanding termination, no-contest, and four communication/acknowledgment atoms. It truly misses four duties, including lead forwarding and noncompetition that Standard captured, and adds nine rights, grants, formalities, or factual representations. Two communication pairings are swapped by the matcher.

## Representative source-grounded examples

### 1. Galacticomm — Tiered access fees and schema completeness

> Horst Entertainment agrees to pay Galactcomm $0.01 (one cent) per access up to 400,000 accesses thereafter payment shall be $0.005 (one-half cent) per access. Horst Entertainment shall send this amount to Galacticomm by no later than Wednesday for accesses used from the previuos week (Monday thru Sunday).

**Gold:** Three atoms: first tier, post-threshold tier, and weekly remittance.

**Standard:** One record merges all three and matches only remittance; IsPostTermination is explicitly false.

**Agentic:** Separates remittance but still merges the two price tiers; all four matched Galacticomm outputs omit IsPostTermination.

**Diagnosis:** Agentic helps decomposition but does not satisfy fully atomic pricing output, and the omitted boolean illustrates the run-wide 5.6% post-termination field coverage.

### 2. Watchit — Reciprocal pre-publicity discussion

> Both parties agree to discuss use of information gathered form this arrangement before using it in any kind of promotional or public message.

**Gold:** One conditional duty for each party.

**Standard:** One both-parties record with empty role IDs; one side unmatched.

**Agentic:** Two role-resolved records; both gold atoms match.

**Diagnosis:** Clear Agentic recall/role-resolution win, offset by three unrelated rights false positives.

### 3. Pacific — Reciprocal mediation

> In the event of a dispute, the parties shall seek mediation at a third country mutually agreed upon.

**Gold:** One mediation duty for ACM and one for SLD.

**Standard:** No mediation output.

**Agentic:** One generic parties-level mediation output matches SLD O006 and leaves ACM O005 unmatched.

**Diagnosis:** Agentic finds the clause but still under-splits reciprocal parties.

### 4. Prime — Liquidity adjustment detail

> This required liquidity"  win reduce dollar-for-dollar with any additional shareholder advance s and increase dollar-for-dollar to a maximum of $21,000,000 with any  repayment of shareholder advances.

**Gold:** A required amount/adjustment detail within gold O003.

**Standard:** O003 is found but the adjustment formula is omitted.

**Agentic:** Emits a separate adjustment record, which is deterministically unmatched as alternate atomization.

**Diagnosis:** Agentic recovers useful detail at the cost of an extra record; its evidence adds only a trailing quotation mark.

### 5. Verso — Further assurance and cost allocation

> Seller will, at Backhaul's cost and expense, do, execute, acknowledge and deliver or cause to be done, executed, acknowledged and delivered, each and all of such further acts, deeds, assignments, transfers, conveyances and assurances as may reasonably be required by Backhaul or Buyer

**Gold:** Seller performance O001 and Backhaul cost-bearing O002.

**Standard:** Captures Seller duty with cost as modifier; O002 unmatched.

**Agentic:** Same result: one Seller duty with cost as modifier; O002 unmatched.

**Diagnosis:** No Agentic improvement; reciprocal cost allocation still needs a separate party record.

### 6. RGC — Base and recurring franchise fees

> For each succeeding calendar year during the term of this Franchise, the total annual Franchise Fee paid by Grantee to the localities shall be the base year total annual Franchise Fee increased by three (3) percent compounded annually over the term of the Franchise.

**Gold:** Separate 2016 base-year O001 and succeeding-year O002 atoms.

**Standard:** Captures only O001; O002 is a true miss.

**Agentic:** One record spans base and future years and matches O002, leaving O001 as an atomicity non-match.

**Diagnosis:** Agentic recovers the omitted clause but still fails year-specific atomization.

### 7. Xlite — Manufacturing and delivery responsibility

> All manufacturing and delivery will be the responsibility of BOSCH.

**Gold:** Separate O006 manufacturing and O007 delivery duties.

**Standard:** No prediction.

**Agentic:** One combined record matches O007 and leaves O006 unmatched.

**Diagnosis:** Material clause-discovery gain, but multi-action splitting remains incomplete.

### 8. Gridiron — Product quality decomposition

> Biomass must contain a minimum of six percent (6%) total Cannabidiol (CBD/and or CBDA) and all Biomass must have less than three percent (3%) total TCH content.

**Gold:** CBD, THC, contaminants, quantity, and sale are details within one gold sale duty O001.

**Standard:** One broad delivery record partially carries quantity/specification context.

**Agentic:** Separate CBD, THC, and contaminant records; the matcher gives O001 to contaminants and counts CBD/THC unmatched.

**Diagnosis:** Several unmatched Agentic records are valid alternate atomization, so 47.6% contract precision understates source-supported usefulness.

### 9. TransMontaigne — Assignment prohibition and exception

> No Party shall have the right to assign its rights or obligations under this Agreement without the consent of the other Parties hereto; provided, however, that either party hereto may make a collateral assignment of this Agreement solely to secure working capital financing for such party.

**Gold:** A prohibition for each party, each carrying the financing exception.

**Standard:** No assignment prediction.

**Agentic:** One generic prohibition record plus one separate permitted-exception/right record; the evaluator matches both O006/O007.

**Diagnosis:** Agentic discovers the clause, but O007 is a semantic false match because the matched prediction describes only the right/exception, not the prohibition.

### 10. PreCheck — Communication form and acknowledgment

> Official communication from Distributor or the Principal shall be in written form or by email, acknowledged by the recipient.

**Gold:** Four atoms: each sender form/channel duty and each recipient acknowledgment duty.

**Standard:** No communication predictions.

**Agentic:** Four role-resolved predictions cover all atoms, but greedy quote ties swap the Principal-send and Principal-acknowledge gold pairings.

**Diagnosis:** Strong practical Agentic gain; pair-level evaluator output is unreliable when all atoms share one quote.

## Evaluator assessment

**Precision:** The 55.8% deterministic precision is conservative because 16/57 unmatched predictions are source-supported alternate atoms, fragments, or evaluator artifacts. It is still directionally fair for raw production usability: all 57 are extra records requiring reconciliation, 41 are genuine non-obligations, and one matched TransMontaigne record is itself an exception/right rather than the gold prohibition.

**Recall:** The 74.2% recall fairly measures compliance with the requested one-party/one-action atomic output, but understates clause discovery. Twenty of 25 misses have 1.0 quote support in an already-used prediction, yielding 92/97 (94.8%) quote-supported clause coverage. Conversely, TransMontaigne O007 is a semantic false match, so 72/97 should not be read as 72 fully correct atomic records.

### Schema-completeness correction

- The corrected evaluator distinguishes field accuracy from field coverage and fails closed when IsPostTermination is missing.
- Standard provides IsPostTermination for all 43 matches and gets 41 correct: 95.3% effective accuracy, 100% coverage.
- Agentic provides IsPostTermination for only 4 of 72 matches; all four are correct, but effective accuracy and coverage are both 5.6%.
- The prior missing-to-false default would have incorrectly credited most omitted Agentic values because most gold records are false.

### Matching artifacts

- All deterministic selected alignments score 1.0 because containment returns 1.0; broad and narrow evidence are therefore tied.
- Greedy reverse tuple ordering selects the narrow TransMontaigne tax item for O003 and leaves the correct broad reimbursement record unmatched.
- TransMontaigne prediction 16 describes only the permitted collateral-assignment exception/right, yet it matches gold O007, whose predicate is the no-assignment prohibition.
- PreCheck communication predictions 20 and 21 are semantically swapped across gold O018/O020 because all four atoms share the same quote; set coverage is correct, pair-level IDs are not.
- Gridiron O001 is assigned to the contaminant fragment while the seller, CBD, and THC components are counted unmatched; this depresses precision without indicating unsupported text.
- Twenty gold atoms are left unmatched solely because one-to-one matching cannot give a merged reciprocal/multi-action prediction credit for more than one atom.

### Evidence and duplicate artifacts

- The 98.18% Agentic groundedness is 162/165.
- All three failures are in Prime and become exact source substrings after removing one extra terminal quotation mark.
- This is a punctuation-normalization artifact, not substantive evidence fabrication.
- duplicate_count=0 only detects identical obligor/summary/first-quote signatures.
- Agentic contains 26 repeated evidence entries within 17 predictions.
- It also contains semantic list fragmentation that the duplicate metric does not detect.

The reported Agentic groundedness failure is not substantive hallucination: 162/165 quotes match exactly, and the other three become exact Prime source substrings after deleting one terminal quotation mark. Agentic does, however, repeat 26 evidence entries across 17 predictions. The evaluator’s duplicate count remains zero because it does not detect repeated evidence or semantic list fragmentation.

### Evaluator changes worth testing

- Replace greedy matching with maximum-weight bipartite assignment plus deterministic semantic tie-breaking.
- Report clause-level many-to-one coverage separately from atomic one-to-one correctness.
- Add parent-clause/group IDs so merged and split outputs can be distinguished from unsupported predictions.
- Cluster semantic fragments/duplicates rather than relying only on exact signatures.
- Normalize harmless terminal quote punctuation for evidence groundedness.
- Keep party/type/nature/detail scoring separate, but add a gated fully-correct-atom metric.

## Gold concerns

**High-confidence valid obligations omitted by gold: 0.** No high-confidence missing gold duty was found among the 57 Agentic unmatched predictions. The gold should not be changed from this review.

- All 107 gold quotes and all source hashes were previously verified.
- The reviewed adjudication notes explicitly exclude passive fee/formality/pricing clauses without a clear performing party, termination and amendment options, present grants/conveyances, legal effects, and factual representations.
- Eight Agentic extras are useful alternate atomization of existing gold, not missing gold obligations.
- Gridiron notice addresses are useful destination details but not separate operative atoms; Agentic evidence contains only address lines.
- Xlite limitations embedded in reserved-right language are arguable covenants, but actor/action semantics are not clear enough for a high-confidence gold addition.

Two borderline items were reviewed but do not justify changing gold:

- **Xlite:** “BOSCH reserves the right to share rights given unless it disrupts and/or interferes with CLIENTS business and/or productivity.” — Could be read as a limitation on BOSCH, but it is framed as a reserved right with an ambiguous condition rather than a clear performance duty; retain as non-gold unless annotation policy changes.
- **Gridiron:** “Shi Farms:214 39t h Lane Pueblo, CO 81006 ... Gridiron: 1119 West 1st Ave - Suite G Spokane, WA 99021” — Valid notice-address detail in context, but not a separate obligation and not supported by an operative quote standing alone.

## Recommendation

**Demo:** Use the paired run only as a candid recall-versus-cost demo. Lead with Agentic's reduction from 33 to 5 true misses and examples like Watchit/PreCheck, while showing the 41 genuine extra non-obligations, matcher artifacts, and 31x token cost. Do not present Agentic as an across-the-board winner.

**Production:** Do not use either raw mode as the production obligation register. Standard can seed a reviewed queue; Agentic can be evaluated as an optional recall escalation, but this run does not validate a production cascade or acceptable unit economics.

### Schema changes to test (not yet run)

- **Require IsPostTermination to be emitted as an explicit boolean on every obligation and add field-coverage validation before accepting a run.** Target: Agentic omits the field on 68/72 matched outputs; corrected accuracy and coverage are 5.6%. _Proposed, unrun._
- **Add explicit ontology exclusions for rights/options, present grants and conveyances, recitals/facts, representations/acknowledgements, legal consequences, jurisdiction/termination powers, and passive amendment formalities.** Target: 41 genuine Agentic unmatched non-obligations. _Proposed, unrun._
- **Require exactly one explicit obligor and one atomic action per obligation; expand each/both/no-party clauses into party-specific records and split coordinated verbs such as defend/indemnify/hold harmless.** Target: 20 Agentic atomicity non-matches. _Proposed, unrun._
- **Require minimal verbatim evidence for the duty, prohibit evidence-only preambles/addresses, deduplicate Evidence entries, and fail validation when obligor or operative quote is missing.** Target: 26 repeated evidence entries, 3 quote/evaluator artifacts, and generic-party outputs. _Proposed, unrun._
- **Clarify that conditions, amounts, timing, exceptions, and adjustment formulas belong on the parent obligation unless they independently assign performance to another party.** Target: Prime, Gridiron, and TransMontaigne fragmentation. _Proposed, unrun._

### Workflow and evaluation experiments (not yet run)

- Use maximum-weight assignment with semantic/party tie-breaking instead of greedy ordering.
- Add clause-group identifiers and report many-to-one clause coverage beside atomic one-to-one scoring.
- Add semantic duplicate/fragment clustering and repeated-evidence metrics.
- Normalize harmless terminal quote punctuation for groundedness.
- Add a fully-correct-atom metric gated on party, nature, type, and required details.
- Test Standard-first extraction followed by Agentic only on low-confidence, reciprocal, or uncovered clauses; compare union recall, review burden, latency, and tokens.
- Run the revised schema on this fixed gold without changing gold, then on a larger contract mix.
- Run N×1 stability tests before making reliability claims.

**Decision:** Agentic materially helps recall, but the evidence—including 5.6% IsPostTermination coverage—does not support production adoption or a claim of material balanced-quality advantage yet.

## Unmatched Agentic prediction appendix

Every unmatched prediction is listed below; repeated identical evidence entries are collapsed for readability.

| Contract | Index | Classification | Prediction summary | Related gold |
|---|---:|---|---|---|
| Galacticomm | 0 | unsupported/right/fact | The agreement states it voids and nullifies all previous agreements to this date between Galacticomm and Horst Entertainment Inc. | — |
| Galacticomm | 1 | unsupported/right/fact | No additional fees of any kind may be paid to Galaticomm, except for fees stated within the agreement for software usage and/or bandwidth usage. | — |
| Galacticomm | 6 | unsupported/right/fact | If Galacticomm, Inc. chooses to terminate the agreement, Horst Entertainment Inc. will have the right to purchase a license copy of the software for $15,000.00. | — |
| Watchit | 2 | unsupported/right/fact | Watchit reserves the right to modify the content to reflect sponsorship by an advertiser and advertisers. | — |
| Watchit | 6 | unsupported/right/fact | Watchit has the exclusive right to sell third party advertising as sponsors of their content and has the right to brand the content under the Watchit brand and place a "bug" on the screen identifying the content with a Watchit trademark. | — |
| Watchit | 9 | unsupported/right/fact | Oceanic Time Warner Cable is able to not include any content that it deems inappropriate or distasteful. | — |
| Pacific | 4 | unsupported/right/fact | Nothing in the Agreement is intended to confer on any party the right to assign its rights or obligations under the Agreement. | — |
| Pacific | 5 | unsupported/right/fact | The Agreement is not intended to confer rights or remedies on persons other than the parties and their respective successors and assigns, and it does not give any third person subrogation or action-over rights. | — |
| Prime | 2 | alternate atom | Once a Project Completion component is satisfied, Prime's absolute and unconditional warranty to Guaranty to fund the payment to Offshore of costs exceeding available commitments (including interest) for that component will expire. | O001 |
| Prime | 4 | alternate atom | The required liquidity will reduce dollar-for-dollar with any additional shareholder advances and increase dollar-for-dollar to a maximum of $21,000,000 with any repayment of shareholder advances. | O003 |
| Prime | 6 | unsupported/right/fact | Prime understands that a breach of obligations under this Agreement would result in an Event of Default under the Credit Agreement with Offshore that would permit Guaranty to pursue its available remedies under the Credit Agreement. | — |
| Prime | 7 | unsupported/right/fact | Offshore is executing this Agreement to acknowledge that a breach of this Agreement would result in an Event of Default under the Credit Agreement. | — |
| Verso | 0 | unsupported/right/fact | Seller must transfer, sell, assign, convey and deliver to Backhaul all right, title and interest in, to and under the Assigned Intellectual Property (including the listed Trademarks, Patents, and associated goodwill). | — |
| RGC | 0 | unsupported/right/fact | Grantor grants to Grantee (and Grantee accepts) a franchise to construct, reconstruct, operate, maintain, repair, and extend a Gas Distribution System within Grantor's Territorial Limits. | — |
| Xlite | 0 | unsupported/right/fact | Audit/access limitation: BOSCH reserves the right to keep product generation and delivery confidential and states it is not available for any type of audit. | — |
| Xlite | 1 | unsupported/right/fact | BOSCH reserves the right to share rights given, unless doing so disrupts or interferes with CLIENTS business and/or productivity. | — |
| Xlite | 2 | unsupported/right/fact | BOSCH grants CLIENT the "Exclusive Distribution License Rights" to sell and distribute the Products within the "Territory". | — |
| Xlite | 3 | unsupported/right/fact | BOSCH grants CLIENT un-exclusive "Reserved Rights" to sell and distribute the "Product" within the "Territory". | — |
| Xlite | 4 | unsupported/right/fact | BOSCH grants Client exclusive rights to sell and distribute the Product (subject to the Territory) to certain select automotive companies, each of which must be approved by Bosch in writing as requested by the Client on a case by case basis. | — |
| Xlite | 5 | unsupported/right/fact | Territory is defined as United States of America and Canada, excluding the US Virgin Islands. | — |
| Xlite | 6 | unsupported/right/fact | Reserved-rights activity is stated to be in concert and approval with BOSCH and limited to any and all of BOSCH's current clients. | — |
| Xlite | 8 | unsupported/right/fact | Cost of product is based upon square inch and is reserved confidentially. | — |
| Xlite | 9 | unsupported/right/fact | The established market price will be negotiated confidentially but will follow the max and min limitations allowed. | — |
| Xlite | 16 | unsupported/right/fact | Examples are provided relating to the city, state and/or federal contract accounts context (exit signs, safety fixtures, freeway signs, etc...). | — |
| Xlite | 18 | duplicate/fragment | Confidentiality clause includes CLIENT acknowledgment that irreparable injury and damage will result from disclosure to any third party of Proprietary Information associated with the Product. | O014, O015 |
| Xlite | 21 | unsupported/right/fact | By signing in the spaces provided below, BOSCH and CLIENT accept and agree to all terms and conditions of the Agreement. | — |
| Gridiron | 0 | alternate atom | Shi Farms agrees to sell Product to Gridiron. | O001 |
| Gridiron | 2 | alternate atom | The purchase price is $5.00 per pound for a total cost of $150,000. | O003 |
| Gridiron | 4 | alternate atom | Biomass must contain a minimum of six percent (6%) total Cannabidiol (CBD/and or CBDA). | O001 |
| Gridiron | 5 | alternate atom | All Biomass must have less than three percent (3%) total TCH content. | O001 |
| Gridiron | 7 | unsupported/right/fact | Buyer may take its own samples (Product Samples) for testing. | — |
| Gridiron | 9 | alternate atom | The point of delivery of Product Samples is a laboratory determined by Gridiron if Gridiron determines third party analysis is required for processing. | O005 |
| Gridiron | 12 | unsupported/right/fact | Either party may terminate the Agreement at any time prior to delivery of the Product. | — |
| Gridiron | 16 | quote/evaluator artifact | Notices to Shi Farms must be sent to the stated address/ATTN. | O012 |
| Gridiron | 17 | quote/evaluator artifact | Notices to Gridiron must be sent to the stated address/ATTN. | O011 |
| Gridiron | 18 | unsupported/right/fact | The Agreement may not be waived, amended or assigned unless there is an agreed written and signed document signed by both parties. | — |
| Gridiron | 20 | unsupported/right/fact | Failure to return the information constitutes a material breach, with all rights and remedies available to the party whose material has been disclosed. | — |
| TransMontaigne | 1 | quote/evaluator artifact | The Operating Company must reimburse EmployeeCo for all direct or indirect costs and expenses incurred by EmployeeCo in connection with performing its obligations under this Agreement. | O003 |
| TransMontaigne | 2 | alternate atom | The Operating Company must make reimbursements to EmployeeCo in advance or immediately upon such costs being incurred, or otherwise in accordance with historical practice, unless otherwise agreed. | O003 |
| TransMontaigne | 3 | duplicate/fragment | The Operating Company must reimburse EmployeeCo for salaries of the Services Employees. | O003 |
| TransMontaigne | 4 | duplicate/fragment | The Operating Company must reimburse EmployeeCo for the cost of employee benefits for the Services Employees, including specified benefits. | O003 |
| TransMontaigne | 5 | duplicate/fragment | The Operating Company must reimburse EmployeeCo for costs associated with workers' compensation claims and other disputes or liabilities associated with the Services Employees. | O003 |
| TransMontaigne | 6 | duplicate/fragment | The Operating Company must reimburse EmployeeCo for severance costs with respect to any terminated Services Employees. | O003 |
| TransMontaigne | 9 | unsupported/right/fact | Each Party submits to the jurisdiction of the state and federal courts in the State of Colorado and to venue in Denver, Colorado. | — |
| TransMontaigne | 11 | unsupported/right/fact | The Agreement may be terminated by the written agreement of the Parties. | — |
| TransMontaigne | 12 | unsupported/right/fact | Either Party may terminate the Agreement upon 5 days written notice to the other Party. | — |
| TransMontaigne | 13 | unsupported/right/fact | The Agreement may be amended or modified from time to time only by the written agreement of all the Parties hereto. | — |
| TransMontaigne | 14 | unsupported/right/fact | Each amendment or addendum instrument must be reduced to writing and designated on its face an "Amendment" or an "Addendum" to this Agreement. | — |
| PreCheck | 0 | unsupported/right/fact | Principal appoints Distributor as a non-exclusive distributor to sell the listed Products. | — |
| PreCheck | 1 | unsupported/right/fact | Principal grants Distributor non-exclusive rights to sell the products within Romania (the Territory). | — |
| PreCheck | 11 | unsupported/right/fact | In the event of termination, Distributor is entitled to receive all orders accepted by Principal prior to the date of termination. | — |
| PreCheck | 15 | unsupported/right/fact | Distributor’s submitted orders are subject to acceptance by Principal in Principal’s sole discretion. | — |
| PreCheck | 16 | unsupported/right/fact | Any change or modification is not valid unless it is in writing and signed by the parties (applies to Principal). | — |
| PreCheck | 17 | unsupported/right/fact | Any change or modification is not valid unless it is in writing and signed by the parties (applies to Distributor). | — |
| PreCheck | 23 | unsupported/right/fact | Principal represents it has the right to enter into the Agreement and that the Agreement does not violate any agreement to which it is a party. | — |
| PreCheck | 24 | unsupported/right/fact | Distributor represents it has the right to enter into the Agreement and that the Agreement does not violate any agreement to which it is a party. | — |
| PreCheck | 25 | unsupported/right/fact | Principal represents that it owns or has rights to the intellectual property embodied in the Products. | — |
