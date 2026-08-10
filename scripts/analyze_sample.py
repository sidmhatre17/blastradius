#!/usr/bin/env python3
"""Analyze all sample PRs against the seeded payorbit repo via HTTP API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PRS = ROOT / "data" / "sample_prs"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    api = args.api.rstrip("/")

    with httpx.Client(timeout=120.0) as client:
        seed = client.post(f"{api}/api/v1/demo/seed")
        seed.raise_for_status()
        repo_id = seed.json()["repo_id"]
        print("repo_id", repo_id)

        expected = json.loads((PRS / "expected.json").read_text())
        results = []
        for name in sorted(PRS.glob("*.diff")):
            diff_text = name.read_text()
            resp = client.post(
                f"{api}/api/v1/analyze",
                json={
                    "repo_id": repo_id,
                    "diff_text": diff_text,
                    "pr_title": name.name,
                    "async": False,
                },
            )
            resp.raise_for_status()
            report = resp.json()
            row = {
                "diff": name.name,
                "score": report.get("risk_score"),
                "tier": report.get("risk_tier"),
                "top_incidents": [
                    i.get("incident_id") for i in (report.get("similar_incidents") or [])[:3]
                ],
            }
            results.append(row)
            print(json.dumps(row))

            rules = expected.get(name.name) or {}
            if "tier_in" in rules and row["tier"] not in rules["tier_in"]:
                print(
                    f"FAIL tier {name.name}: {row['tier']} not in {rules['tier_in']}",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            if "min_score" in rules and (row["score"] or 0) < rules["min_score"]:
                print(f"FAIL score {name.name}", file=sys.stderr)
                raise SystemExit(1)
            if "max_score" in rules and (row["score"] or 0) > rules["max_score"]:
                print(f"FAIL max_score {name.name}", file=sys.stderr)
                raise SystemExit(1)
            for need in rules.get("incident_top3") or []:
                if need not in row["top_incidents"]:
                    print(f"FAIL incident {name.name} missing {need}", file=sys.stderr)
                    raise SystemExit(1)

    print("analyze-sample OK")


if __name__ == "__main__":
    main()
