# BlastRadius

**Know what your PR might break — before it merges.**

Paste a unified diff → BlastRadius maps service/file blast radius, retrieves similar past incidents, scores risk with explainable features, and returns an evidence-linked report.

> Demo GIF: add `docs/demo.gif` after recording a local run (Seed → `pr_common_client.diff` → Analyze).

## Honest positioning

BlastRadius is **not** a new category invention. Tools like Arbor, CodeDig, and CodeRadius already explore change impact / blast radius. This project’s angle is a **demoable, open stack** that combines:

1. **Import-graph blast radius** (static, deterministic)
2. **Incident-memory retrieval** with overlap boost
3. **Explainable risk score** (weights fixed; LLM only writes prose)

See [docs/competitors.md](docs/competitors.md).

## Architecture

```text
UI (Streamlit) / curl
        │
 FastAPI (/api/v1)
        │
 ┌──────┼──────────────┐
 │      │              │
Repo   Incident     Analyze
Ingest Ingest      Orchestrator
 │      │              │
 Code  Incident     Risk Scorer
 Graph Embeddings   + Explainer
 │      │              │
 PostgreSQL + Chroma + Redis + sample PayOrbit files
```

Details: [docs/architecture.md](docs/architecture.md)

## Risk model (v1)

| Factor | Weight |
|--------|--------|
| `shared_library_touch` | 0.25 |
| `incident_heat` | 0.25 |
| `critical_service_touch` | 0.15 |
| `fan_out_degree` | 0.15 |
| `config_or_migration` | 0.10 |
| `test_gap` | 0.10 |

Score is **deterministic**. The LLM/template never chooses `risk_score` or `affected_services`.  
Full formulas: [docs/risk_model.md](docs/risk_model.md)

## Quickstart ($0 local)

**Recommended on Apple Silicon:** Docker for Postgres + Redis only; API/UI on the host.

```bash
cp .env.example .env
make up
uv sync --extra dev
make migrate

# terminal 1
make api

# terminal 2 (optional UI)
make ui
```

One-shot seed + gold recall (CI-safe, no paid APIs):

```bash
APP_MODE=ci EMBEDDING_PROVIDER=hash LLM_PROVIDER=template make eval-gold
```

With API already running:

```bash
make seed
make analyze-sample
```

### Modes

| Mode | Embeddings | Explainer | Notes |
|------|------------|-----------|-------|
| `local` (default) | sentence-transformers `bge-small` | Ollama (template fallback) | Full demo, $0 |
| `ci` | HashEmbedder | TemplateExplainer | No model downloads |
| `cloud` | optional | optional OpenAI | **Not required** |

Ollama (optional prose):

```bash
brew install ollama
ollama serve
ollama pull qwen2.5:7b-instruct
```

First local embedding run downloads `BAAI/bge-small-en-v1.5` from Hugging Face once (free). After changing `EMBEDDING_MODEL` / provider, re-run seed (`make seed`) so Chroma collections rebuild.

Walkthrough: [docs/demo_script.md](docs/demo_script.md)

## Sample results (PayOrbit)

Seeded fictional fintech monorepo + 12 incidents + 6 sample PR diffs.

| Diff | Expectation |
|------|-------------|
| `pr_safe_docs.diff` | low tier |
| `pr_common_client.diff` | high/critical + `INC-0991` in top3 |
| `pr_auth_middleware.diff` | high/critical + `INC-1042` in top3 |
| `pr_billing_retry.diff` | medium+ + `INC-0888` in top3 |

Fill live numbers in `artifacts/demo_report.md` and `artifacts/eval_recall.md` after `make eval-gold`.

## Limitations

- Python (+ YAML/JSON/MD paths) only in MVP
- Blast radius = **imports + path heuristics**, not call graphs / pointer analysis
- Dynamic imports invisible
- Sample world is curated for a credible demo — disclosed here on purpose
- CI hash embeddings are weak semantically; overlap boost + file metadata carry recall
- Risk weights are heuristics, not calibrated to a production org

## Roadmap

- GitHub Check / App comment bot
- Richer call-graph backends
- JS/TS support
- Map suggested tests to real pytest node ids

## License

MIT — see [LICENSE](LICENSE)
