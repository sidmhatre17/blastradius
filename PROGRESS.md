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
| 3 | `feat: add payorbit sample world and expected fixtures` | **Pushed** | `bdb3829` (+ `PROGRESS.md`) |
| 4 | `feat: parse diffs and build import graph` | **Ready to commit** | local; verified |
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
- Health: `GET /health` (DB probe when Postgres up)

### DB + Alembic (commit 2)

- Domain enums + models: `Repo`, `FileNode`, `Edge`, `Incident`, `IncidentChunk`, `CodeChunk`, `Analysis`
- Cascades: repo delete → files/edges/analyses/code_chunks; **incidents independent of repo**
- Alembic revision `499df124434b_initial_schema`; `make migrate`
- Tests: `tests/test_models.py`

### PayOrbit sample world (commit 3)

- `data/sample_repo/`, 12 incidents, 6 diffs, `expected.json`, `seed_manifest.json`
- **7** locked `http_client` importers

### Diff + import graph (commit 4 — pending push)

| Module | Path |
|--------|------|
| Diff parser | `src/blastradius/services/diff_parser.py` |
| Import parser | `src/blastradius/services/import_parser.py` |
| Code graph / blast radius | `src/blastradius/services/code_graph.py` |
| Repo ingest (Postgres) | `src/blastradius/services/repo_ingest.py` |
| Repos API | `src/blastradius/api/repos.py` |

**API**

- `POST /api/v1/repos/ingest` `{name, path}` (path allowlisted under `SAMPLE_ROOT` / `REPOS_PATH`)
- `GET /api/v1/repos`, `GET /api/v1/repos/{id}`
- `GET /api/v1/repos/{id}/graph?depth=&seed=`

**Behavior locked in**

- Fan-out = **importers** (edges into file)
- Blast BFS prefers **reverse imports**; `packages/**` seeds pull all importers
- Virtual `belongs_to` edges in graph projection
- Ingest stores files/edges/code_chunks in Postgres; **Chroma upsert deferred to commit 5**
- Owners from `SERVICE_OWNERS.yaml` → `Repo.owners_json`

**Verified**

- `pytest`: 17 passed
- `ruff`: clean
- API smoke: ingest PayOrbit → graph seed `http_client` → **7 importers**

---

## Current work / next actions

1. Commit/push slice 4 after owner OK
2. Next: **incident ingest + embeddings (ST/hash) + Chroma + retrieval + overlap boost** (plan commit 5)

---

## Do not recreate

- Do not re-scaffold compose/settings/health
- Do not re-author DB models/migration `499df124434b`
- Do not regenerate PayOrbit trees/importers/gold incidents — calibrate sample data later if needed
- Do not reimplement diff/import/graph parsers once commit 4 lands
- Do not `gh repo create`; remote already exists
- Do not commit `PROJECT_BLASTRADIUS_PLAN.md`
- Do not require paid APIs for MVP

---

## Local runtime notes

- Prefer: `make up` (postgres+redis) → `uv sync --extra dev` → `make migrate` → `make api`
- `.env` is gitignored (copy from `.env.example`)
- Docker must be running for datastore verification
