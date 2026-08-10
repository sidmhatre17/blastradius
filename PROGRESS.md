# BlastRadius — Build Progress

Living log of what exists so we don’t recreate work or lose context.
Update this file **at the end of every slice**, before asking to commit.

Remote: https://github.com/sidmhatre17/blastradius.git  
Plan (local only, not in repo): `/Users/sid/Documents/resume/updated/PROJECT_BLASTRADIUS_PLAN.md`  
Conflict order: **§32 > §31 > §29 > earlier**

---

## Owner preferences (locked)

| Preference | Choice |
|------------|--------|
| Workspace | `/Users/sid/Documents/resume/blastradius` |
| Branch | `main` |
| Plan file in repo | **No** |
| Topology | Docker = postgres+redis only; api/worker/ui on host via `uv`; Ollama on host |
| Commit / push gates | Ask before commit; ask before push |
| Attribution | No Cursor trailers (strip via `commit-tree` if injected) |

Durable rules: `.cursor/rules/blastradius-workflow.mdc`

---

## Commit map status (plan §25.4)

| # | Commit | Status | SHA / notes |
|---|--------|--------|-------------|
| 1 | scaffold | **Pushed** | `541a162` |
| 2 | db models + alembic | **Pushed** | `f4e3d13` |
| 3 | payorbit sample world | **Pushed** | `bdb3829` |
| 4 | diffs + import graph | **Pushed** | `bbb4b10` |
| 5 | incident ingest + retrieval | **Pushed** | `9bd3f92` |
| 6 | risk scorer v1 | **Pushed** | `19da17b` |
| 7 | analyze API + explainers + worker | **Ready to commit** | verified |
| 8 | streamlit demo ui | Not started | |
| 9 | docs | Not started | |
| 10 | eval harness | Not started | |
| 11 | release v0.1.0 | Not started | |

---

## What already exists (through 6)

Full ingest/retrieval/scoring stack + PayOrbit fixtures + expected.json gates.

### Analyze + explainers + worker (commit 7 — pending)

| Piece | Path |
|-------|------|
| Template + Ollama explainers | `services/explainer.py` (`explain_with_fallback`) |
| Analyze orchestrator | `services/analyze.py` (cache key includes `scorer_version=v1`) |
| API | `POST/GET /api/v1/analyze` (`async` bool) |
| arq worker | `workers/settings.py` — `make worker` |
| Tests | `tests/test_explainer.py`, `tests/test_analyze.py` |

**Behavior:** sync analyze is default; async enqueues `run_analysis` to Redis/arq. LLM failure → template fallback. CI uses template. `cost_usd=0.0`. Diff limit 500KB.

**Verified:** 30 tests passed (`APP_MODE=ci`), ruff clean; safe PR low vs common-client high/critical.

---

## Current work / next actions

1. Commit/push slice 7 after owner OK
2. Next: **Streamlit demo UI**

---

## Do not recreate

- Do not change scorer weights without owner approval
- Do not reimplement prior slices
- Do not commit the plan markdown file

---

## Local runtime notes

```bash
make up && make migrate
make api          # host
make worker       # host (needed only for async analyze)
APP_MODE=ci EMBEDDING_PROVIDER=hash LLM_PROVIDER=template uv run pytest -q
```
