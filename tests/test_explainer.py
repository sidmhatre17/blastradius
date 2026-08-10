from blastradius.config import Settings
from blastradius.services.explainer import TemplateExplainer, explain_with_fallback


def test_template_explainer_uses_only_evidence() -> None:
    evidence = {
        "risk_score": 78,
        "risk_tier": "high",
        "changed_files": ["packages/common/http_client.py"],
        "affected_services": ["common", "api_gateway"],
        "similar_incidents": [
            {
                "incident_id": "INC-0991",
                "title": "Shared client",
                "score": 0.9,
                "why": "file_overlap",
                "snippet": "retries",
            }
        ],
        "risk_factors": [
            {"name": "shared_library_touch", "weight": 0.25, "value": 1.0, "contribution": 0.25}
        ],
    }
    out = TemplateExplainer().explain(evidence)
    assert "78" in out.summary
    assert "INC-0991" in out.summary
    assert out.suggested_tests
    assert out.residual_risks
    assert out.provider == "template"


def test_explain_fallback_on_ci_settings() -> None:
    settings = Settings(app_mode="ci", llm_provider="ollama")
    out = explain_with_fallback(
        {
            "risk_score": 10,
            "risk_tier": "low",
            "changed_files": ["README.md"],
            "affected_services": [],
            "similar_incidents": [],
            "risk_factors": [],
        },
        settings,
    )
    assert out.provider == "template"
