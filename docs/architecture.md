# Architecture

## Components

| Component | Role |
|-----------|------|
| FastAPI (`/api/v1`) | Ingest, analyze, demo seed, health |
| PostgreSQL | Repos, files, import edges, incidents, analyses |
| Chroma | `code_chunks` + `incident_chunks` vectors (cosine) |
| Redis + arq | Optional async analyze jobs |
| Streamlit UI | Demo: seed → pick PR → report |
| Ollama (host) | Optional JSON explanations; template fallback always works |

## Analyze pipeline

```text
diff_text
  → parse changed files (unidiff)
  → map paths → services (path rules)
  → expand blast radius (depth=2, cap=50; reverse imports primary)
  → query pack → retrieve incidents (top 8) + code chunks (top 8)
  → overlap boost / metadata expansion
  → deterministic risk score + six factors
  → explainer (Ollama or template)
  → persist Analysis.report_json
```

## Design rules

1. **Score is deterministic** from features. LLM does not set `risk_score` or `affected_services`.
2. LLM/template may only write `summary`, `suggested_tests`, `residual_risks` (and optional why text).
3. If LLM is down → **TemplateExplainer**; analysis still succeeds.
4. MVP graph = import edges + belongs_to (virtual for UI) + shared-package fan-out.
5. Incidents are a **global demo corpus** (no FK to repo). Repo delete cascades files/edges/chunks/analyses only.
6. Embedding model id is stamped on Chroma collections; mismatch → drop + rebuild on ingest/seed.

## Process topology (Mac)

Preferred:

1. `docker compose up` → **postgres**, **redis**
2. Host: `make api`, `make worker` (async only), `make ui`
3. Ollama on host at `127.0.0.1:11434`

## Key modules

```text
src/blastradius/
  api/           health, repos, incidents, analyze, demo
  services/      diff/import/graph, ingest, embeddings, vector_store,
                 retrieval, risk_scorer, explainer, analyze
  workers/       arq WorkerSettings
  db/            SQLAlchemy models + session
apps/ui/app.py   Streamlit demo
scripts/         eval_gold.py, analyze_sample.py
data/            PayOrbit sample_repo, incidents, PRs
```

## Caching

Analyze cache key: `sha256(repo_id + diff_text + app_mode + scorer_version)` with `scorer_version=v1`.
