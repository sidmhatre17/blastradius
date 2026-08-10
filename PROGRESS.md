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
| Commit gate | Ask before every local commit |
| Push gate | Ask after owner review |
| Attribution | No Cursor/AI mentions; strip auto `Co-authored-by: Cursor` via `commit-tree` before push |

Durable rules: `.cursor/rules/blastradius-workflow.mdc`

---

## Commit map status (plan §25.4)

| # | Commit | Status | SHA / notes |
|---|--------|--------|-------------|
| 1 | `chore: scaffold blastradius compose and settings` | **Pushed** | `541a162` |
| 2 | `chore: add db models and alembic migration` | **Pushed** | `f4e3d13` |
| 3 | `feat: add payorbit sample world and expected fixtures` | **Pushed** | `bdb3829` |
| 4 | `feat: parse diffs and build import graph` | **Pushed** | `bbb4b10` |
| 5 | `feat: incident ingest and boosted retrieval` | **Pushed** | `9bd3f92` |
| 6 | `feat: deterministic risk scorer v1` | **Ready to commit** | verified |
| 7 | `feat: analyze API worker and explainers` | Not started | |
| 8 | `feat: streamlit demo ui` | Not started | |
| 9 | `docs: readme demo script and competitor notes` | Not started | |
| 10 | `chore: add eval harness and demo artifacts templates` | Not started | |
| 11 | `chore: release v0.1.0` | Not started | |

---

## What already exists

### Through commit 5

- Health, repos API, incidents API, PayOrbit sample world
- Diff/import/graph, embeddings (ST/Hash/Ollama), Chroma, retrieval + overlap boost
- Postgres + Alembic

### Risk scorer v1 (commit 6 — pending push)

- `services/risk_scorer.py` — locked weights §11.7, all six factors, docs-only `incident_heat=0` / `test_gap=0`
- `SCORER_VERSION = "v1"`
- Tests: `tests/test_risk_scorer.py`, `tests/test_expected_bands.py` (expected.json gates)
- **Sample calibration (not weight changes):**
  - `INC-1042` severity → `critical` (so auth middleware PR can reach high with locked formula)
  - Retrieval: exact file-overlap floors similarity at `0.85` before boost (CI hash mode)

**Verified:** 27 tests passed (`APP_MODE=ci`), ruff clean; expected.json bands OK.

---

## Current work / next actions

1. Commit/push slice 6 after owner OK
2. Next: **analyze API + TemplateExplainer + OllamaExplainer + arq worker**

---

## Do not recreate

- Do not change scorer **weights** unless all expected.json fails and owner approves; prefer sample/retrieval calibration
- Do not reimplement prior slices
- Do not commit `PROJECT_BLASTRADIUS_PLAN.md`

---

## Local runtime notes

- `make up` → `make migrate` → `make api`
- CI: `APP_MODE=ci EMBEDDING_PROVIDER=hash`
- Chroma: `./data/chroma` (gitignored)
