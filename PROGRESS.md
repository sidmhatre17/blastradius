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
| 5 | `feat: incident ingest and boosted retrieval` | **Ready to commit** | verified locally |
| 6 | `feat: deterministic risk scorer v1` | Not started | |
| 7 | `feat: analyze API worker and explainers` | Not started | |
| 8 | `feat: streamlit demo ui` | Not started | |
| 9 | `docs: readme demo script and competitor notes` | Not started | |
| 10 | `chore: add eval harness and demo artifacts templates` | Not started | |
| 11 | `chore: release v0.1.0` | Not started | |

---

## What already exists

### Through commit 4

- FastAPI health + repos ingest/list/get/graph
- Diff/import parsers, code graph (reverse-import BFS), PayOrbit sample world
- Postgres models + Alembic `499df124434b`

### Incident ingest + retrieval (commit 5 — pending push)

| Module | Path |
|--------|------|
| Embeddings | `services/embeddings.py` — `HashEmbedder`, `STEmbedder`, `OllamaEmbedder`, `build_embedder` |
| Vector store | `services/vector_store.py` — Chroma `code_chunks` / `incident_chunks`, cosine, stamp drop+rebuild |
| Incident ingest | `services/incident_ingest.py` — frontmatter validate, chunk, upsert |
| Retrieval | `services/retrieval.py` — query pack, overlap boost (+0.15 file / +0.10 service), metadata candidate expansion for CI |
| API | `api/incidents.py` — `POST /incidents/ingest`, `GET /incidents`, `GET /incidents/{id}` |
| Repo ingest | now also upserts **code** vectors to Chroma |

**CI recall:** HashEmbedder + overlap boost + DB metadata expansion so gold incidents land in top3 without model downloads.

**Verified:** `APP_MODE=ci` → **22 tests passed**, ruff clean. Gold pairs INC-0991 / INC-1042 / INC-0888 in top3.

---

## Current work / next actions

1. Commit/push slice 5 after owner OK
2. Next: **deterministic risk scorer v1** + expected.json band tests

---

## Do not recreate

- Do not re-scaffold / re-author models migration / PayOrbit trees / diff-graph parsers
- Do not reimplement embeddings/vector/retrieval once commit 5 lands
- Do not commit `PROJECT_BLASTRADIUS_PLAN.md` or require paid APIs

---

## Local runtime notes

- `make up` → `make migrate` → `make api`
- CI tests: `APP_MODE=ci EMBEDDING_PROVIDER=hash`
- Local demo embeddings: sentence-transformers (downloads once)
- Chroma path: `./data/chroma` (gitignored)
