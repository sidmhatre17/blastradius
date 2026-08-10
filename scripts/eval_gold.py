#!/usr/bin/env python3
"""Gold-pair recall@3 harness. Writes artifacts/eval_recall.md."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from blastradius.config import Settings, get_settings
from blastradius.db.session import get_session_factory, reset_engine
from blastradius.services.analyze import create_analysis, run_analysis
from blastradius.services.embeddings import build_embedder
from blastradius.services.vector_store import VectorStore

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPECTED = ROOT / "data" / "sample_prs" / "expected.json"
DEFAULT_OUT = ROOT / "artifacts" / "eval_recall.md"

# Gold pairs used when expected.json omits incident_top3
GOLD_PAIRS = [
    ("pr_common_client.diff", ["INC-0991"]),
    ("pr_auth_middleware.diff", ["INC-1042"]),
    ("pr_billing_retry.diff", ["INC-0888"]),
]


async def _ensure_seeded(settings: Settings) -> str:
    from httpx import ASGITransport, AsyncClient

    from blastradius.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/demo/seed")
        resp.raise_for_status()
        return resp.json()["repo_id"]


async def run_eval(expected_path: Path, out_path: Path) -> dict:
    settings = get_settings()
    # Prefer CI-safe defaults when APP_MODE=ci
    store = VectorStore(settings=settings, embedder=build_embedder(settings))
    await reset_engine()

    expected = json.loads(expected_path.read_text())
    pairs: list[tuple[str, list[str]]] = []
    for name, rules in expected.items():
        if "incident_top3" in rules:
            pairs.append((name, list(rules["incident_top3"])))
    if not pairs:
        pairs = GOLD_PAIRS

    # Seed via service layer if API app path is heavy; use demo endpoint through ASGI.
    repo_id = await _ensure_seeded(settings)

    factory = get_session_factory(settings)
    rows: list[dict] = []
    hits = 0
    async with factory() as session:
        from uuid import UUID

        rid = UUID(repo_id)
        for diff_name, need in pairs:
            diff_text = (ROOT / "data" / "sample_prs" / diff_name).read_text()
            analysis = await create_analysis(
                session,
                repo_id=rid,
                diff_text=diff_text,
                pr_title=diff_name,
                settings=settings,
            )
            if analysis.status != "completed":
                analysis = await run_analysis(
                    session, analysis.id, settings=settings, vector_store=store
                )
            report = analysis.report_json or {}
            top3 = [x["incident_id"] for x in (report.get("similar_incidents") or [])[:3]]
            ok = all(i in top3 for i in need)
            hits += int(ok)
            rows.append(
                {
                    "diff": diff_name,
                    "need": need,
                    "top3": top3,
                    "ok": ok,
                    "tier": report.get("risk_tier"),
                    "score": report.get("risk_score"),
                }
            )

    total = len(pairs)
    recall = (hits / total * 100.0) if total else 0.0
    lines = [
        "# Eval recall@3",
        "",
        f"- Mode: `{settings.app_mode}`",
        f"- Pairs: {total}",
        f"- Hits: {hits}",
        f"- Recall@3: **{recall:.1f}%**",
        "",
        "| Diff | Required | Top3 | Score | Tier | Pass |",
        "|------|----------|------|-------|------|------|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['diff']}` | {', '.join(r['need'])} | "
            f"{', '.join(r['top3']) or '—'} | {r['score']} | {r['tier']} | "
            f"{'yes' if r['ok'] else 'no'} |"
        )
    lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return {"recall_pct": recall, "hits": hits, "total": total, "out": str(out_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=Path, default=DEFAULT_EXPECTED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    result = asyncio.run(run_eval(args.expected, args.out))
    print(
        f"recall@3={result['recall_pct']:.1f}% "
        f"({result['hits']}/{result['total']}) -> {result['out']}"
    )
    if result["total"] and result["hits"] < result["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
