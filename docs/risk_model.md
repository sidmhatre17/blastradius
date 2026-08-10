# Risk model v1

Scorer version string: **`v1`** (included in analyze cache keys).

## Weights (sum = 1.0)

| Feature | Weight |
|---------|--------|
| `shared_library_touch` | 0.25 |
| `incident_heat` | 0.25 |
| `critical_service_touch` | 0.15 |
| `fan_out_degree` | 0.15 |
| `config_or_migration` | 0.10 |
| `test_gap` | 0.10 |

Every report includes **all six** factors with `weight`, `value`, `contribution=weight*value`, and `evidence`.

## Feature values ∈ [0, 1]

1. **shared_library_touch** — `1.0` if any changed path starts with `packages/`, else `0.0`.
2. **incident_heat** — for top-3 similar incidents after rerank:  
   `heat_i = similarity_i * severity_weight_i`, then `max(heat_i)`.  
   **Hard rule:** if **all** changed files are docs → force `0.0` (retrieval may still run for UI).
3. **critical_service_touch** — `max(criticality_weight)` among affected services (from owners YAML / blast radius).
4. **fan_out_degree** — `min(1.0, m/6.0)` where `m` = max **importer** count among changed files (edges into the file).
5. **config_or_migration** — `1.0` if any changed file is config or migration.
6. **test_gap** — `1.0` if there is a non-docs code change and no test file in the diff; docs-only → `0.0`.

### Criticality / severity maps

```text
low=0.25, medium=0.5, high=0.75, critical=1.0
```

## Score → tier

```text
raw = Σ weight_i * value_i
risk_score = round(100 * raw)

low      ≤ 24
medium   25–49
high     50–74
critical ≥ 75
```

## Calibration policy

If `data/sample_prs/expected.json` fails after seeding, **prefer adjusting sample fan-out / incident overlaps / diffs**, not weight hacks. Weight changes require an explicit update here and owner approval.

## Retrieval inputs to heat

Overlap boost (locked):

- +0.15 file intersection with changed files
- +0.10 service intersection with affected services
- clamp to 1.0

Exact file overlap also floors similarity at `0.85` before boost (helps HashEmbedder / CI).
