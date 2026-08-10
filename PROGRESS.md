# BlastRadius — Build Progress

Living log of what exists so we don’t recreate work or lose context.
Update this file **at the end of every slice**, before asking to commit.

Remote: https://github.com/sidmhatre17/blastradius.git  
Plan (local only): `/Users/sid/Documents/resume/updated/PROJECT_BLASTRADIUS_PLAN.md`  
Conflict order: **§32 > §31 > §29 > earlier**

---

## Owner preferences (locked)

| Preference | Choice |
|------------|--------|
| Workspace | `/Users/sid/Documents/resume/blastradius` |
| Branch | `main` |
| Topology | Docker postgres+redis; api/worker/ui on host via `uv` |
| Commit / push | Ask first |
| Attribution | No Cursor trailers |

---

## Commit map status

| # | Commit | Status | SHA |
|---|--------|--------|-----|
| 1–6 | scaffold → scorer | **Pushed** | through `19da17b` |
| 7 | analyze API + explainers + worker | **Pushed** | `e28f2d2` |
| 8 | streamlit demo ui | **Ready to commit** | verified |
| 9 | docs | Not started | |
| 10 | eval harness | Not started | |
| 11 | release v0.1.0 | Not started | |

---

## Streamlit UI (commit 8 — pending)

- `apps/ui/app.py` — single-page demo:
  1. Health + Seed PayOrbit (calls repos/incidents ingest)
  2. Sample PR dropdown + paste diff
  3. Score / tier / summary
  4. Factors table
  5. Similar incidents
  6. Blast radius (`streamlit-agraph` if installed, else tables)
  7. Session history (in-memory; no list API yet)
- Default analyze is **sync** + spinner; optional async poll checkbox
- `make ui` sets `API_BASE_URL`; `.env.example` documents it

**Verified:** ruff clean; full pytest still green (30). UI is thin client — no new backend tests required.

---

## Next

1. Commit/push UI slice
2. `/demo/seed` + `make demo` (plan item 15)
3. Docs + eval harness + polish

---

## Local demo path

```bash
make up && make migrate
make api          # terminal 1
make ui           # terminal 2
# optional async: make worker
```

Open http://127.0.0.1:8501 → Seed → pick `pr_common_client.diff` → Analyze.
