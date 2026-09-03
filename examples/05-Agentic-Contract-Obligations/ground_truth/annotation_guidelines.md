# Atomic obligation annotation

Annotate one JSON object per contract with `doc_id`, `source_text`, `parties`, and `obligations`.

For each obligation:

- Split compound clauses when action, obligor, trigger, timing, amount, or exception differs.
- Resolve `obligor_party_id` and `obligee_party_ids` only to annotated contracting parties.
- Copy one or more contiguous `exact_quote` spans character-for-character. Never stitch spans or add ellipses.
- Record `required_fields` from `trigger_condition`, `timing`, `amount_or_quantity`, `exceptions`, and `related_obligation_ids` only when the gold clause requires them.
- Use the analyzer taxonomy exactly.
- Do not infer generalized risk, playbook deviation, or operational fulfillment.
- Have a second reviewer verify party identity, atomization, and every quote before marking `review_status` as `verified`.

Minimal obligation shape:

```json
{
  "obligation_id": "O1",
  "obligor_party_id": "P1",
  "obligee_party_ids": ["P2"],
  "obligation_type": "Payment",
  "nature": "Conditional",
  "exact_quotes": ["exact contiguous contract text"],
  "trigger_condition": "stated trigger",
  "timing": "stated deadline",
  "amount_or_quantity": "stated amount",
  "exceptions": "",
  "related_obligation_ids": [],
  "required_fields": ["trigger_condition", "timing", "amount_or_quantity"]
}
```
