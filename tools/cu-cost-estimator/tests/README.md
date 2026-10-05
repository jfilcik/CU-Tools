# Offline cost tests

From the repository root, run this suite in a separate Python process:

```powershell
python -m pytest tools\cu-cost-estimator\tests -q --basetemp tools\cu-cost-estimator\tests\.test-work -o cache_dir=tools\cu-cost-estimator\tests\.pytest-cache -o "markers=unit: offline unit tests"
```

No Azure credentials, official CLI installation, service access or network is
required. CLI integration tests launch only the local offline Python helpers.

- `test_cost_estimator.py`: preserved schema/default/explicit-usage estimation,
  configured pricing arithmetic, feature multipliers, scaling and legacy
  explicit batch behavior. Pricing fixtures are illustrative, not current
  Azure billing assertions.
- `test_result_costs.py`: native and legacy usage locations; recursive result
  discovery without double-counting; report/schema exclusion; repeated basename
  identity; missing/incomplete usage versus actual zero; invalid/unknown pricing;
  nonzero malformed-input exits; machine-readable stdout; saved text output.

The shared result loader's format and typed-field tests live in
`tools\cu-results-export\tests` and should be run separately.
See the [tool README](../README.md) for supported usage contracts and coverage
limitations.
