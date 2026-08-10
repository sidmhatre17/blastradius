# Demo script

Target: ~5–10 minutes live or recorded.

## Setup (once)

```bash
cp .env.example .env
make up
uv sync --extra dev
make migrate
```

Optional Ollama for nicer summaries:

```bash
ollama serve
ollama pull qwen2.5:7b-instruct
```

## Run

```bash
# terminal 1
make api

# terminal 2
make ui
```

Open http://127.0.0.1:8501

## Talk track

1. **Problem** — Engineers merge without knowing blast radius or prior incidents near the change.
2. **Seed** — Click “Seed PayOrbit”. Explain fictional fintech monorepo + 12 incident docs.
3. **Safe PR** — Select `pr_safe_docs.diff` → Analyze. Expect **low** score; docs-only forces `incident_heat=0` / `test_gap=0`.
4. **Risky PR** — Select `pr_common_client.diff`. Show:
   - high/critical score
   - `shared_library_touch` + fan-out (≥6 importers of `http_client`)
   - similar incident **INC-0991**
   - blast radius pulling gateway / billing / notify
5. **Explainability** — Factor table is the product; summary text is secondary (template or Ollama).
6. **Honesty** — Category exists (Arbor et al.); differentiator is incident memory + open deterministic scoring.

## CLI alternative (no UI)

```bash
make seed
make analyze-sample
make eval-gold
```

## Async path (optional)

```bash
make worker   # terminal 3
```

In UI, enable “Async analyze” (sleep-polls `GET /analyze/{id}`).
