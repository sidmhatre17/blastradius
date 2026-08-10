# BlastRadius

Know what your PR might break — before it merges.

> Scaffold in progress. Full quickstart lands with the docs slice.

## Local topology (recommended on Apple Silicon)

- **Docker:** Postgres + Redis only (`make up`)
- **Host:** API / worker / UI via `uv run`
- **Ollama:** on host (optional for explanations; template fallback always works)

```bash
cp .env.example .env
make up
uv sync --extra dev
make api
```

Health: `GET http://127.0.0.1:8000/health`
