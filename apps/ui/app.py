from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PRS = ROOT / "data" / "sample_prs"
SAMPLE_REPO = ROOT / "data" / "sample_repo"
SAMPLE_INCIDENTS = ROOT / "data" / "sample_incidents"

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "")


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    return headers


def api(method: str, path: str, **kwargs: Any) -> httpx.Response:
    url = f"{API_BASE}{path}"
    return httpx.request(method, url, headers=_headers(), timeout=120.0, **kwargs)


def list_sample_prs() -> list[str]:
    if not SAMPLE_PRS.exists():
        return []
    return sorted(p.name for p in SAMPLE_PRS.glob("*.diff"))


def load_pr_diff(name: str) -> str:
    return (SAMPLE_PRS / name).read_text(encoding="utf-8")


def render_blast_radius(blast: dict[str, Any]) -> None:
    nodes = blast.get("nodes") or []
    edges = blast.get("edges") or []
    try:
        from streamlit_agraph import Config, Edge, Node, agraph

        a_nodes = [
            Node(
                id=n["id"],
                label=n.get("label") or n["id"],
                size=20 if n.get("type") == "service" else 12,
            )
            for n in nodes
        ]
        a_edges = [
            Edge(source=e["from"], target=e["to"], label=e.get("reason") or "")
            for e in edges
        ]
        config = Config(width=800, height=420, directed=True, physics=True)
        agraph(nodes=a_nodes, edges=a_edges, config=config)
    except Exception:
        st.caption("Graph library unavailable — showing adjacency tables.")
        if nodes:
            st.dataframe(pd.DataFrame(nodes), use_container_width=True)
        if edges:
            st.dataframe(pd.DataFrame(edges), use_container_width=True)


def analyze_sync(repo_id: str, diff_text: str, pr_title: str) -> dict[str, Any]:
    resp = api(
        "POST",
        "/api/v1/analyze",
        json={
            "repo_id": repo_id,
            "diff_text": diff_text,
            "pr_title": pr_title or None,
            "async": False,
        },
    )
    resp.raise_for_status()
    return resp.json()


def analyze_async_poll(repo_id: str, diff_text: str, pr_title: str) -> dict[str, Any]:
    resp = api(
        "POST",
        "/api/v1/analyze",
        json={
            "repo_id": repo_id,
            "diff_text": diff_text,
            "pr_title": pr_title or None,
            "async": True,
        },
    )
    resp.raise_for_status()
    body = resp.json()
    analysis_id = body.get("analysis_id")
    if body.get("status") == "completed":
        return body
    if not analysis_id:
        return body
    deadline = time.time() + 120
    status_box = st.empty()
    while time.time() < deadline:
        got = api("GET", f"/api/v1/analyze/{analysis_id}")
        got.raise_for_status()
        payload = got.json()
        status = payload.get("status")
        status_box.info(f"Analysis status: {status}")
        if status in {"completed", "failed"}:
            return payload
        time.sleep(1.0)
    raise TimeoutError("async analysis timed out after 120s")


def seed_demo() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    repo_resp = api(
        "POST",
        "/api/v1/repos/ingest",
        json={"name": "payorbit", "path": str(SAMPLE_REPO.resolve())},
    )
    repo_resp.raise_for_status()
    inc_resp = api(
        "POST",
        "/api/v1/incidents/ingest",
        json={"path": str(SAMPLE_INCIDENTS.resolve())},
    )
    inc_resp.raise_for_status()
    return repo_resp.json(), inc_resp.json()


def main() -> None:
    st.set_page_config(page_title="BlastRadius", layout="wide")
    st.title("BlastRadius")
    st.caption("Know what your PR might break — before it merges.")
    st.write(f"API: `{API_BASE}`")

    # --- Status / seed ---
    st.header("1. Seed / status")
    cols = st.columns(3)
    with cols[0]:
        if st.button("Check health"):
            try:
                health = api("GET", "/health").json()
                st.json(health)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Health check failed: {exc}")
    with cols[1]:
        if st.button("Seed PayOrbit (repo + incidents)"):
            with st.spinner("Seeding…"):
                try:
                    repo, incidents = seed_demo()
                    st.session_state["repo_id"] = repo["id"]
                    st.success(
                        f"Seeded repo `{repo['name']}` ({repo['id']}) and "
                        f"{len(incidents)} incidents."
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Seed failed: {exc}")
    with cols[2]:
        try:
            repos = api("GET", "/api/v1/repos").json()
        except Exception:
            repos = []
        repo_labels = {
            f"{r['name']} ({r['id'][:8]}…) [{r['status']}]": r["id"] for r in repos
        }
        if repo_labels:
            choice = st.selectbox("Active repo", list(repo_labels))
            st.session_state["repo_id"] = repo_labels[choice]
        elif "repo_id" in st.session_state:
            st.write(f"Repo id: `{st.session_state['repo_id']}`")
        else:
            st.info("No repos yet — seed PayOrbit first.")

    # --- Diff input ---
    st.header("2. Sample PR / paste diff")
    pr_names = list_sample_prs()
    selected = st.selectbox("Sample PR", ["(paste only)", *pr_names])
    default_diff = ""
    if selected != "(paste only)":
        default_diff = load_pr_diff(selected)
    title_default = selected if selected != "(paste only)" else ""
    pr_title = st.text_input("PR title (optional)", value=title_default)
    diff_text = st.text_area("Unified diff", value=default_diff, height=240)
    use_async = st.checkbox("Async analyze (poll worker)", value=False)

    if st.button("Analyze", type="primary"):
        repo_id = st.session_state.get("repo_id")
        if not repo_id:
            st.error("Select or seed a repo first.")
        elif not diff_text.strip():
            st.error("Diff text is required.")
        else:
            try:
                with st.spinner("Analyzing..."):
                    if use_async:
                        report = analyze_async_poll(repo_id, diff_text, pr_title)
                    else:
                        report = analyze_sync(repo_id, diff_text, pr_title)
                st.session_state["last_report"] = report
                history = st.session_state.setdefault("history", [])
                history.insert(
                    0,
                    {
                        "analysis_id": report.get("analysis_id"),
                        "risk_score": report.get("risk_score"),
                        "risk_tier": report.get("risk_tier"),
                        "pr_title": pr_title,
                    },
                )
                st.session_state["history"] = history[:20]
            except Exception as exc:  # noqa: BLE001
                st.error(f"Analyze failed: {exc}")

    report = st.session_state.get("last_report")
    if not report:
        st.stop()

    if report.get("status") == "failed":
        st.error(report.get("error") or "Analysis failed")
        st.json(report)
        st.stop()

    # --- Score ---
    st.header("3. Score")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Risk score", report.get("risk_score"))
    m2.metric("Tier", report.get("risk_tier"))
    m3.metric("Latency (ms)", report.get("latency_ms"))
    m4.metric("Mode", report.get("mode"))
    st.write(report.get("summary") or "")

    # --- Factors ---
    st.header("4. Risk factors")
    factors = report.get("risk_factors") or []
    if factors:
        st.dataframe(pd.DataFrame(factors), use_container_width=True)

    # --- Incidents ---
    st.header("5. Similar incidents")
    incidents = report.get("similar_incidents") or []
    if incidents:
        st.dataframe(pd.DataFrame(incidents), use_container_width=True)
    else:
        st.write("No similar incidents.")

    # --- Blast radius ---
    st.header("6. Blast radius")
    blast = report.get("blast_radius") or {}
    render_blast_radius(blast)

    st.subheader("Suggested tests")
    for item in report.get("suggested_tests") or []:
        st.write(f"- {item}")
    st.subheader("Residual risks")
    for item in report.get("residual_risks") or []:
        st.write(f"- {item}")

    # --- Session history ---
    st.header("7. Session history")
    hist = st.session_state.get("history") or []
    if hist:
        st.dataframe(pd.DataFrame(hist), use_container_width=True)
    else:
        st.write("No analyses in this session yet.")


if __name__ == "__main__":
    main()
