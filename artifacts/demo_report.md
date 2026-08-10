# Demo report placeholder — filled after a local `make demo` / analyze run.

## Sample metrics (fill in)

- Indexed files / services / incidents: `__` / `__` / `__`
- `pr_common_client.diff` score: `__` / 100
- `pr_safe_docs.diff` score: `__` / 100
- Incident recall@3: see `eval_recall.md`
- p95 sync analyze latency (sample PRs): `__` ms

## Notes

Run:

```bash
make up && make migrate
make api   # other terminal
make seed && make analyze-sample && make eval-gold
```
