# BlastRadius — Build Progress

Living log of what exists so we don’t recreate work or lose context.
Update this file **at the end of every slice**, before asking to commit.

Remote: https://github.com/sidmhatre17/blastradius.git  
Plan (local only): `/Users/sid/Documents/resume/updated/PROJECT_BLASTRADIUS_PLAN.md`

---

## Commit map

| # | Commit | Status | SHA |
|---|--------|--------|-----|
| 1–8 | scaffold → streamlit UI | **Pushed** | through `2a5cb5a` |
| 9 | docs (README/competitors/…) | Not started | |
| 10 | demo seed + eval harness | **Ready to commit** | verified |
| 11 | release v0.1.0 | Not started | |

---

## This slice (pending commit)

- `POST /api/v1/demo/seed` — idempotent PayOrbit repo + incidents
- `scripts/eval_gold.py` — recall@3 → `artifacts/eval_recall.md` (gitignored output)
- `scripts/analyze_sample.py` — HTTP analyze all sample PRs vs expected.json
- `artifacts/demo_report.md` — metrics template (tracked)
- Makefile: `seed`, `analyze-sample`, `eval-gold`, `demo` helpers
- Test: `tests/test_demo_seed.py`

**Verified:** 31 tests passed; `eval_gold` recall@3 = **100%** (3/3) in `APP_MODE=ci`.

---

## Next

1. Commit/push this slice
2. Docs: README, architecture, risk_model, demo_script, competitors

---

## Demo commands

```bash
make up && make migrate
make api                 # terminal 1
make seed && make analyze-sample
make eval-gold           # in-process seed+recall (CI-friendly)
make ui                  # terminal 2
```
