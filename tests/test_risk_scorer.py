from blastradius.services.diff_parser import ChangedFile
from blastradius.services.retrieval import SimilarIncident
from blastradius.services.risk_scorer import score_risk, tier_for_score


def _cf(path: str, *, docs=False, test=False, config=False, migration=False) -> ChangedFile:
    return ChangedFile(
        path=path,
        is_added=False,
        is_removed=False,
        is_modified=True,
        is_test=test,
        is_config=config,
        is_migration=migration,
        is_docs=docs,
        added_lines=1,
        removed_lines=1,
    )


def test_tier_boundaries() -> None:
    assert tier_for_score(0) == "low"
    assert tier_for_score(24) == "low"
    assert tier_for_score(25) == "medium"
    assert tier_for_score(49) == "medium"
    assert tier_for_score(50) == "high"
    assert tier_for_score(74) == "high"
    assert tier_for_score(75) == "critical"
    assert tier_for_score(100) == "critical"


def test_docs_only_forces_incident_heat_and_test_gap_zero() -> None:
    changed = [_cf("README.md", docs=True)]
    similar = [
        SimilarIncident(
            incident_id="INC-0991",
            title="x",
            score=0.99,
            why="semantic",
            snippet="x",
            severity="critical",
            files=["packages/common/http_client.py"],
            services=["common"],
        )
    ]
    result = score_risk(
        changed,
        affected_services=[],
        importer_counts={},
        similar_incidents=similar,
        owners_json={"services": {}},
    )
    by_name = {f.name: f for f in result.risk_factors}
    assert by_name["incident_heat"].value == 0.0
    assert by_name["test_gap"].value == 0.0
    assert result.risk_tier == "low"
    assert result.risk_score <= 24


def test_shared_library_and_fan_out() -> None:
    changed = [_cf("packages/common/http_client.py")]
    result = score_risk(
        changed,
        affected_services=["common"],
        importer_counts={"packages/common/http_client.py": 7},
        similar_incidents=[],
        owners_json={
            "services": {"common": {"criticality": "critical"}},
        },
    )
    by_name = {f.name: f for f in result.risk_factors}
    assert by_name["shared_library_touch"].value == 1.0
    assert by_name["fan_out_degree"].value == 1.0
    assert by_name["critical_service_touch"].value == 1.0
    assert by_name["test_gap"].value == 1.0
    assert len(result.risk_factors) == 6
    assert result.risk_score >= 60


def test_six_factors_always_present() -> None:
    result = score_risk(
        [],
        affected_services=[],
        importer_counts={},
        similar_incidents=[],
        owners_json=None,
    )
    assert [f.name for f in result.risk_factors] == [
        "shared_library_touch",
        "incident_heat",
        "critical_service_touch",
        "fan_out_degree",
        "config_or_migration",
        "test_gap",
    ]
