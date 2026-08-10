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
| Attribution | No Cursor/AI mentions in repo text; no `Co-authored-by: Cursor` trailers (strip via `commit-tree` if hooks re-inject). Historical scaffold commit may still have trailer — leave it |

Durable rules: `.cursor/rules/blastradius-workflow.mdc`

---

## Commit map status (plan §25.4)

| # | Commit | Status | SHA / notes |
|---|--------|--------|-------------|
| 1 | `chore: scaffold blastradius compose and settings` | **Pushed** | `541a162` (may include historical Cursor trailer — leave as-is) |
| 2 | `chore: add db models and alembic migration` | **Pushed** | `f4e3d13` (trailer-free) |
| 3 | `feat: add payorbit sample world and expected fixtures` | **Ready to commit** (local, uncommitted) | See Current work |
| 4 | `feat: parse diffs and build import graph` | Not started | |
| 5 | `feat: incident ingest and boosted retrieval` | Not started | |
| 6 | `feat: deterministic risk scorer v1` | Not started | |
| 7 | `feat: analyze API worker and explainers` | Not started | |
| 8 | `feat: streamlit demo ui` | Not started | |
| 9 | `docs: readme demo script and competitor notes` | Not started | |
| 10 | `chore: add eval harness and demo artifacts templates` | Not started | |
| 11 | `chore: release v0.1.0` | Not started | |

---

## What already exists

### Scaffold (commit 1)

- `pyproject.toml` + `uv.lock`, `Makefile`, `Dockerfile`, `docker-compose.yml`
- Compose default services: **postgres**, **redis**; api/worker/ui under profile `full`
- `.env.example`, `.gitignore`, `LICENSE`, minimal `README.md`
- Package: `src/blastradius/` with `config.py`, `deps.py`, `main.py`, `api/health.py`
- Placeholders: `apps/ui/app.py`, `artifacts/.gitkeep`, `scripts/.gitkeep`
- Health: `GET /health` (later upgraded to probe DB)

### DB + Alembic (commit 2)

- Domain enums: `src/blastradius/domain/enums.py` (`RepoStatus`, `EdgeType`, `Severity`, `RiskTier`, `AnalysisStatus`, `AppMode`)
- Models: `Repo`, `FileNode`, `Edge`, `Incident`, `IncidentChunk`, `CodeChunk`, `Analysis`
- Cascades: repo delete → files/edges/analyses/code_chunks; **incidents independent of repo**
- Session: `src/blastradius/db/session.py` (`check_db`, async engine)
- Alembic: `alembic.ini`, `alembic/env.py` (async), revision `499df124434b_initial_schema`
- `make migrate` → `uv run alembic upgrade head`
- Tests: `tests/test_models.py` (4 unit tests)
- Health returns `db: ok` when Postgres is up

### PayOrbit sample world (pending commit 3)

Paths under `data/`:

| Path | Contents |
|------|----------|
| `data/sample_repo/` | Full PayOrbit tree + `SERVICE_OWNERS.yaml` |
| `data/sample_incidents/` | **12** markdown incidents (`INC-0410` … `INC-1042`) |
| `data/sample_prs/` | **6** diffs + `expected.json` |
| `data/seed_manifest.json` | Seed paths, importer lock list, gold IDs |

**Locked `http_client` importers (7):**

1. `services/api_gateway/app.py`
2. `services/api_gateway/auth/middleware.py`
3. `services/api_gateway/routes/billing.py`
4. `services/billing_worker/worker.py`
5. `services/billing_worker/retry.py`
6. `services/notify_service/sender.py`
7. `services/auth_service/validate.py`

**Sample PRs:** `pr_safe_docs`, `pr_notify_copy`, `pr_auth_middleware`, `pr_common_client`, `pr_billing_retry`, `pr_mixed`

**Gold incident links:** INC-1042↔auth middleware, INC-0991↔http_client, INC-0888↔billing retry, plus distractors INC-0666/INC-0650

Verified locally: importer count ≥6, hotspot LOC 30–80, diff paths resolve, frontmatter keys present.

---

## Current work / next actions

1. Commit slice 3: sample world **+ this `PROGRESS.md`** (after owner OK)
2. Push when owner says push
3. Next build slice: **diff parser + import parser + repo ingest + graph tests** (plan commit 4)

---

## Do not recreate

- Do not re-scaffold compose/settings/health
- Do not re-author DB models/migration `499df124434b`
- Do not regenerate PayOrbit paths/importers/gold incidents once commit 3 lands — calibrate later by editing sample data if scorer gates fail, not by inventing parallel trees
- Do not `gh repo create`; remote already exists
- Do not commit `PROJECT_BLASTRADIUS_PLAN.md`
- Do not require paid APIs for MVP

---

## Local runtime notes

- Prefer: `make up` (postgres+redis) → `uv sync --extra dev` → `make migrate` → `make api`
- `.env` is gitignored (copy from `.env.example`)
- Docker must be running for datastore verification
